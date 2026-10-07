"""Key-holding proxy for a hosted OpenAI-compatible LLM API (default: Groq).

Why this exists: the app container is the lab's intentionally exploitable
host -- a student who reaches code execution there can read its environment
and files. The real API key therefore lives ONLY in this process (run on the
host, outside the container) and is injected into upstream requests here.
The app talks to http://127.0.0.1:11435/v1 with no key at all.

The proxy only forwards POST /v1/chat/completions, pins the model, and caps
max_tokens, so even someone who reaches it from inside the container can't
use it for much beyond what the chatbot itself can do.

Config (env or .env.llm next to this repo, never .env):
  LLM_UPSTREAM_KEY    required, your Groq key
  LLM_UPSTREAM_URL    default https://api.groq.com/openai/v1
  LLM_MODEL           default liquid/lfm-2.5-2.6b:free
  LLM_PROXY_PORT      default 11435 (bound to 127.0.0.1 only)
  LLM_MAX_TOKENS      default 400 (upper bound on per-request max_tokens)
  LLM_MAX_CONCURRENCY default 2 (simultaneous upstream calls)
"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def _load_env_file():
    path = Path(__file__).resolve().parent.parent / ".env.llm"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env_file()
KEY = os.environ.get("LLM_UPSTREAM_KEY", "")
UPSTREAM = os.environ.get("LLM_UPSTREAM_URL", "https://api.groq.com/openai/v1").rstrip("/")
MODEL = os.environ.get("LLM_MODEL", "liquid/lfm-2.5-2.6b:free")
PORT = int(os.environ.get("LLM_PROXY_PORT", "11435"))
MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "400"))
MAX_BODY = 256 * 1024
# Free tiers rate-limit per key. Cap simultaneous upstream calls and, on a
# 429, wait out the upstream Retry-After (bounded) and retry, so a burst of
# users queues briefly instead of erroring.
_slots = threading.BoundedSemaphore(int(os.environ.get("LLM_MAX_CONCURRENCY", "2")))
_RETRIES = int(os.environ.get("LLM_PROXY_RETRIES", "4"))
_MAX_WAIT = float(os.environ.get("LLM_PROXY_MAX_WAIT", "15"))


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body: bytes, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # /v1/models doubles as the app's health check and lets an operator
        # see which models the upstream key can use. Falls back to the
        # pinned model if upstream can't be reached.
        req = urllib.request.Request(
            f"{UPSTREAM}/models",
            headers={"Authorization": f"Bearer {KEY}", "User-Agent": "shop-lab-llm-proxy/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return self._send(200, r.read())
        except Exception:
            self._send(200, json.dumps({"data": [{"id": MODEL}]}).encode())

    def do_POST(self):
        if self.path.rstrip("/") != "/v1/chat/completions":
            return self._send(404, b'{"error":"not found"}')
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY:
            return self._send(413, b'{"error":"bad size"}')
        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return self._send(400, b'{"error":"bad json"}')
        payload["model"] = MODEL
        payload["stream"] = False
        payload["max_tokens"] = min(int(payload.get("max_tokens") or MAX_TOKENS), MAX_TOKENS)

        req = urllib.request.Request(
            f"{UPSTREAM}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {KEY}",
                "User-Agent": "shop-lab-llm-proxy/1.0",
            },
            method="POST",
        )
        for attempt in range(_RETRIES + 1):
            try:
                with _slots:
                    with urllib.request.urlopen(req, timeout=60) as r:
                        return self._send(r.status, r.read())
            except urllib.error.HTTPError as e:
                ra = e.headers.get("retry-after")
                if e.code == 429 and attempt < _RETRIES:
                    try:
                        wait = float(ra) if ra else 2 ** attempt
                    except ValueError:
                        wait = 2 ** attempt
                    time.sleep(min(wait, _MAX_WAIT))
                    continue
                extra = {"Retry-After": ra} if ra else {}
                return self._send(e.code, e.read() or b'{"error":"upstream"}', extra)
            except Exception as e:  # network/timeouts -> 502
                return self._send(502, json.dumps({"error": f"upstream failure: {e}"}).encode())

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    if not KEY:
        sys.exit("LLM_UPSTREAM_KEY is not set (put it in .env.llm, not .env).")
    print(f"llm proxy on 127.0.0.1:{PORT} -> {UPSTREAM} model={MODEL}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
