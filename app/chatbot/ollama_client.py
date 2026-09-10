"""Thin HTTP client for the local Ollama server.

The LLM has zero direct access to the database or filesystem -- it only
ever sees text. All real work happens in app/tools/*, invoked by
app/chatbot/agent.py based on tool_calls the model returns.
"""
import requests

from app.config import config


class OllamaError(RuntimeError):
    pass


def chat(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """Call POST /api/chat and return the assistant message dict."""
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
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
    try:
        resp = requests.get(f"{config.OLLAMA_URL.rstrip('/')}/api/tags", timeout=3)
        return resp.status_code == 200
    except requests.RequestException:
        return False
