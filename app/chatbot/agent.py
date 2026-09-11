"""Chatbot orchestration: user <-> Ollama <-> tools <-> database.

Trust-boundary design (see docs/defensive-controls.md):
  - The model NEVER receives database credentials or direct DB access.
  - For SCOPED_TOOLS, this module -- not the model -- decides whose data is
    being requested: it always injects the authenticated session user's id
    and strips any user_id/customer_id argument the model tried to supply.
  - knowledge_base_search has no such scoping (see app/tools/knowledge_base_search.py).
    That single gap is the lab's deliberate vulnerability.

Conversation state is kept in-memory per logged-in user id. This is a lab,
not a production chat service -- history is not persisted across restarts.
"""
import json

from app.chatbot.ollama_client import OllamaError, chat
from app.chatbot.prompts import SYSTEM_PROMPT
from app.logging_setup import detect_suspicious_text, log_event
from app.tools import SCOPED_TOOLS, TOOL_FUNCTIONS, TOOL_SCHEMAS

MAX_TOOL_ITERATIONS = 6
MAX_HISTORY_MESSAGES = 20

_conversations: dict[int, list[dict]] = {}


def _allowed_arg_keys(tool_name: str) -> set:
    for schema in TOOL_SCHEMAS:
        fn = schema["function"]
        if fn["name"] == tool_name:
            return set(fn.get("parameters", {}).get("properties", {}).keys())
    return set()


def _dispatch_tool(tool_name: str, raw_args, user: dict, request_id: str):
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            raw_args = {}
    if not isinstance(raw_args, dict):
        raw_args = {}

    allowed = _allowed_arg_keys(tool_name)
    clean_args = {k: v for k, v in raw_args.items() if k in allowed}

    func = TOOL_FUNCTIONS.get(tool_name)
    if func is None:
        log_event("tool_invocation_error", tool=tool_name, reason="unknown_tool", request_id=request_id)
        return {"error": f"unknown tool: {tool_name}"}

    if tool_name in SCOPED_TOOLS:
        # Authorization decided here, server-side -- NOT by the model.
        clean_args.pop("user_id", None)
        clean_args.pop("customer_id", None)
        result = func(user_id=user["id"], **clean_args)
    else:
        # knowledge_base_search: no scoping applied. Deliberate. See module docstring.
        result = func(**clean_args)

    log_event(
        "tool_invocation",
        tool=tool_name,
        args=clean_args,
        user_id=user["id"],
        request_id=request_id,
    )
    return result


def handle_chat_message(user: dict, user_message: str, request_id: str) -> str:
    hits = detect_suspicious_text(user_message)
    if hits:
        log_event(
            "suspicious_input_pattern",
            user_id=user["id"],
            patterns=hits,
            request_id=request_id,
            source="user_message",
        )

    history = _conversations.setdefault(user["id"], [{"role": "system", "content": SYSTEM_PROMPT}])
    history.append({"role": "user", "content": user_message})

    log_event("chatbot_request", user_id=user["id"], request_id=request_id, message_len=len(user_message))

    final_text = None
    final_turn_recorded = False
    for _ in range(MAX_TOOL_ITERATIONS):
        try:
            message = chat(history, tools=TOOL_SCHEMAS)
        except OllamaError as exc:
            log_event("chatbot_error", user_id=user["id"], request_id=request_id, error=str(exc))
            final_text = (
                "Sorry, the support assistant is temporarily unavailable "
                "(could not reach the local Ollama model)."
            )
            break

        history.append(message)
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            final_text = message.get("content", "")
            final_turn_recorded = True
            break

        for call in tool_calls:
            fn = call.get("function", {})
            tool_name = fn.get("name", "")
            tool_args = fn.get("arguments", {})
            result = _dispatch_tool(tool_name, tool_args, user, request_id)

            result_text = json.dumps(result)
            hits = detect_suspicious_text(result_text)
            if hits:
                log_event(
                    "suspicious_input_pattern",
                    user_id=user["id"],
                    patterns=hits,
                    request_id=request_id,
                    source=f"tool_result:{tool_name}",
                )

            # The retrieved tool result is appended to the conversation as
            # plain conversational context, exactly like a normal message --
            # there is no separate "untrusted data" channel. This is what
            # lets injected instructions inside retrieved content influence
            # subsequent model behavior.
            history.append({"role": "tool", "name": tool_name, "content": result_text})

    if final_text is None:
        final_text = "Sorry, I wasn't able to finish handling that request. Please try rephrasing."

    if not final_turn_recorded:
        # Only the error/exhausted-iterations paths reach here -- the normal
        # path already appended the model's own assistant message above, so
        # appending it again would duplicate every reply in history.
        history.append({"role": "assistant", "content": final_text})
    if len(history) > MAX_HISTORY_MESSAGES:
        _conversations[user["id"]] = [history[0]] + history[-(MAX_HISTORY_MESSAGES - 1):]

    log_event("chatbot_response", user_id=user["id"], request_id=request_id, response_len=len(final_text))
    return final_text


def reset_conversation(user_id: int):
    _conversations.pop(user_id, None)


def reset_all_conversations():
    """Clear every user's in-memory history. Conversation state lives only
    in this process (see module docstring), so a lab reset that only
    touches the database/filesystem leaves it untouched -- this is what
    scripts/reset_lab.sh calls (via the loopback-only endpoint in
    app/routes/api_chat.py) to actually clear it.
    """
    _conversations.clear()


def get_visible_history(user_id: int) -> list[dict]:
    """Return just the user/assistant turns (no system prompt, no raw tool
    results) so the frontend can re-render a conversation after a page
    navigation. Conversation state already lives server-side per user_id
    (see module docstring) -- this just exposes the customer-facing half of
    it, the same content that already appeared in that customer's own chat
    widget, nothing new.
    """
    history = _conversations.get(user_id, [])
    return [
        {"role": m["role"], "content": m.get("content", "")}
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
