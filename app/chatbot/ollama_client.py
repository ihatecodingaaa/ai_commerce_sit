"""Thin HTTP client for the chat model backend.

Two backends, picked by LLM_BACKEND: the local Ollama server (default) or
any OpenAI-compatible /chat/completions endpoint (e.g. Groq, normally
reached through the key-holding proxy in scripts/llm_proxy.py).

The LLM has zero direct access to the database or filesystem -- it only
ever sees text. All real work happens in app/tools/*, invoked by
app/chatbot/agent.py based on tool_calls the model returns.
"""
import json
import time

import requests

from app.config import config


class OllamaError(RuntimeError):
    pass


def chat(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """Return the assistant message dict ({"content", optional "tool_calls"})."""
    if config.LLM_BACKEND == "openai":
        return _chat_openai(messages, tools)
    return _chat_ollama(messages, tools)


def _to_openai_messages(messages: list[dict]) -> list[dict]:
    """Convert Ollama-style history to OpenAI-style.

    Differences: tool_call arguments must be a JSON string, and tool
    results must reference a tool_call_id. The history here has neither,
    so ids are synthesized by pairing each assistant tool call with the
    tool result that follows it, in order. Tool results whose call was
    trimmed out of history are dropped (the API rejects them).
    """
    out: list[dict] = []
    pending: list[str] = []
    counter = 0
    for m in messages:
        role = m.get("role")
        if role == "assistant" and m.get("tool_calls"):
            calls = []
            pending = []
            for call in m["tool_calls"]:
                fn = call.get("function", {})
                args = fn.get("arguments", {})
                counter += 1
                cid = call.get("id") or f"call_{counter}"
                pending.append(cid)
                calls.append(
                    {
                        "id": cid,
                        "type": "function",
                        "function": {
                            "name": fn.get("name", ""),
                            "arguments": args if isinstance(args, str) else json.dumps(args),
                        },
                    }
                )
            out.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": calls})
        elif role == "tool":
            if not pending:
                continue
            out.append(
                {"role": "tool", "tool_call_id": pending.pop(0), "content": m.get("content", "")}
            )
        else:
            out.append({"role": role, "content": m.get("content", "")})
    return out


def _chat_openai(messages: list[dict], tools: list[dict] | None) -> dict:
    payload = {
        "model": config.LLM_MODEL,
        "messages": _to_openai_messages(messages),
        "max_tokens": config.OLLAMA_NUM_PREDICT,
    }
    if tools:
        payload["tools"] = tools
    headers = {"Content-Type": "application/json"}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"

    resp = None
    for attempt in range(config.LLM_MAX_RETRIES + 1):
        try:
            resp = requests.post(
                f"{config.LLM_BASE_URL.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
                timeout=config.OLLAMA_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise OllamaError(f"LLM request failed: {exc}") from exc
        # Free tiers rate-limit per key; back off briefly and retry.
        if resp.status_code == 429 and attempt < config.LLM_MAX_RETRIES:
            try:
                delay = float(resp.headers.get("retry-after", 2 ** attempt))
            except ValueError:
                delay = 2 ** attempt
            time.sleep(min(delay, 8))
            continue
        break
    try:
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise OllamaError(f"LLM request failed: {exc}") from exc

    data = resp.json()
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        raise OllamaError(f"Unexpected LLM response: {data}")

    result = {"role": "assistant", "content": message.get("content") or ""}
    tool_calls = []
    for call in message.get("tool_calls") or []:
        fn = call.get("function", {})
        args = fn.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args or "{}")
            except json.JSONDecodeError:
                args = {}
        tool_calls.append({"function": {"name": fn.get("name", ""), "arguments": args}})
    if tool_calls:
        result["tool_calls"] = tool_calls
    return result


def _chat_ollama(messages: list[dict], tools: list[dict] | None) -> dict:
    """Call POST /api/chat and return the assistant message dict."""
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": config.OLLAMA_KEEP_ALIVE,
        "options": {
            "num_ctx": config.OLLAMA_NUM_CTX,
            "num_predict": config.OLLAMA_NUM_PREDICT,
        },
    }
    if tools:
        payload["tools"] = tools

    try:
        resp = requests.post(
            f"{config.OLLAMA_URL.rstrip('/')}/api/chat",
            json=payload,
            timeout=config.OLLAMA_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise OllamaError(f"Ollama request failed: {exc}") from exc

    data = resp.json()
    message = data.get("message")
    if not message:
        raise OllamaError(f"Unexpected Ollama response: {data}")
    return message


def is_reachable() -> bool:
    if config.LLM_BACKEND == "openai":
        try:
            # Reachability of the proxy/endpoint only; 401/404 still means "up".
            requests.get(config.LLM_BASE_URL.rstrip("/") + "/models", timeout=3)
            return True
        except requests.RequestException:
            return False
    try:
        resp = requests.get(f"{config.OLLAMA_URL.rstrip('/')}/api/tags", timeout=3)
        return resp.status_code == 200
    except requests.RequestException:
        return False
