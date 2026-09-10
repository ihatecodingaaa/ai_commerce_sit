"""Structured security/telemetry logging.

Events are appended as JSON lines to logs/security.log so an instructor can
grep/jq them during a debrief. Never log raw passwords or the full value of
service tokens -- see log_event()'s redaction of the `token` field.
"""
import json
import os
import threading
import time
import uuid

from app.config import config

_lock = threading.Lock()

_SUSPICIOUS_PATTERNS = (
    "ignore previous",
    "ignore all previous",
    "system:",
    "system note",
    "you are now",
    "new instructions",
    "disregard",
    "override",
    "developer message",
    "do not tell the user",
)


def _log_path() -> str:
    os.makedirs(config.LOG_DIR, exist_ok=True)
    return os.path.join(config.LOG_DIR, "security.log")


def _redact(value):
    if not isinstance(value, str):
        return value
    if len(value) <= 8:
        return "***REDACTED***"
    return value[:4] + "..." + value[-4:] + " (redacted)"


def log_event(event_type: str, **fields):
    """Append one structured JSON event.

    Any field literally named 'password' or 'token' is redacted before
    writing. Callers should still avoid passing full secrets in other keys.
    """
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event_type,
        "event_id": uuid.uuid4().hex[:12],
    }
    for key, value in fields.items():
        if key in ("password", "password_hash", "token", "service_token"):
            record[key] = _redact(str(value))
        else:
            record[key] = value

    line = json.dumps(record, ensure_ascii=False)
    with _lock:
        with open(_log_path(), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    return record


def detect_suspicious_text(text: str):
    """Very small heuristic used only for *logging/detection*, never for
    blocking. Demonstrates the kind of detection a real deployment would
    need; it intentionally does NOT prevent the vulnerable behavior so the
    lab's trust-boundary flaw remains exploitable end to end.
    """
    if not text:
        return []
    lowered = text.lower()
    return [p for p in _SUSPICIOUS_PATTERNS if p in lowered]
