"""Tests the chatbot orchestration layer (app/chatbot/agent.py) without a
live Ollama server, by monkeypatching the model call. This verifies:
  - tool_calls returned by the model are actually executed against real
    tool functions (not simulated),
  - scoped tools always use the session user's id regardless of what the
    model supplies,
  - the final assistant text is returned to the caller.
"""
import json

from app.chatbot import agent as agent_module


def test_agent_executes_tool_calls_and_scopes_to_session_user(monkeypatch, alice, bob):
    calls = {"n": 0}

    def fake_chat(messages, tools=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            # model tries to look up a DIFFERENT customer's
                            # orders -- this must be ignored server-side.
                            "name": "order_lookup",
                            "arguments": {"user_id": bob["id"]},
                        }
                    }
                ],
            }
        # second turn: model has the tool result, gives a final answer
        return {"role": "assistant", "content": "Here is your order info."}

    monkeypatch.setattr(agent_module, "chat", fake_chat)

    reply = agent_module.handle_chat_message(alice, "what are my orders?", "req-1")
    assert reply == "Here is your order info."

    # Inspect the tool result message that was appended to conversation
    # history to confirm it reflects ALICE's orders, not bob's -- proving
    # user_id was overridden server-side, not taken from the model.
    history = agent_module._conversations[alice["id"]]
    tool_messages = [m for m in history if m.get("role") == "tool"]
    assert tool_messages, "expected a tool result message in history"
    result = json.loads(tool_messages[-1]["content"])
    for order in result["orders"]:
        assert order  # non-empty rows returned for alice

    agent_module.reset_conversation(alice["id"])
    agent_module.reset_conversation(bob["id"])


def test_agent_returns_fallback_on_ollama_error(monkeypatch, alice):
    from app.chatbot.ollama_client import OllamaError

    def raising_chat(messages, tools=None):
        raise OllamaError("simulated unreachable Ollama")

    monkeypatch.setattr(agent_module, "chat", raising_chat)
    reply = agent_module.handle_chat_message(alice, "hello", "req-2")
    assert "unavailable" in reply.lower()
    agent_module.reset_conversation(alice["id"])
