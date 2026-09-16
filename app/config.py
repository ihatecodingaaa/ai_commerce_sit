"""Central configuration for the shop-lab application.

All values are read from environment variables (see .env.example). Nothing
here should ever be a real credential -- this is a self-contained training
lab (see SECURITY.md).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "lab-not-a-real-secret-change-me")

    FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(os.environ.get("FLASK_PORT", "5000"))
    FLASK_DEBUG = _bool("FLASK_DEBUG", "false")

    DATABASE_PATH = str(BASE_DIR / os.environ.get("DATABASE_URL", "database/shop_lab.db"))

    OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
    # qwen2.5:1.5b, not the earlier default of qwen2.5:3b -- same family/
    # tokenizer/chat template, so tool-calling shape and instruction-
    # following behavior (including following instructions embedded in
    # retrieved content, which the Stage 4/5 injection depends on) carry
    # over, but roughly half the parameters to run through on a CPU-only
    # 2 vCPU box. If injection reliability ever looks materially worse than
    # qwen2.5:3b in practice, that's the first thing to revert.
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")
    OLLAMA_TIMEOUT_SECONDS = int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "60"))
    # How long Ollama keeps the model loaded in memory after a request.
    # Ollama's own default (5m) means any gap longer than that -- a student
    # reading a reply, writing a follow-up, crafting an injected review --
    # pays a full cold-load (reading model weights back into RAM) on the
    # *next* message on top of inference itself. That reload, not raw
    # token-generation speed, is most of what made replies feel like they
    # took "1-2 minutes": see .env.example.
    OLLAMA_KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "30m")
    # Caps the context window and the length of a single reply. Actual
    # usage here (system prompt + 5 tool schemas + <=20 history messages +
    # a few retrieved KB articles) comfortably fits well under 4096 tokens;
    # letting Ollama fall back to a model's much larger default context
    # allocates a bigger KV-cache than this app ever needs, which costs
    # real time per generated token on CPU. num_predict keeps a verbose
    # reply from running long when the system prompt already asks for
    # "concise" answers but doesn't enforce it.
    OLLAMA_NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", "4096"))
    OLLAMA_NUM_PREDICT = int(os.environ.get("OLLAMA_NUM_PREDICT", "400"))

    # The catalog-sync-service credential is NOT a static config value. It
    # is generated at seed time and rotated automatically on a timer -- see
    # app/services/credentials.py and app/services/rotation.py. This
    # setting only controls how often that background rotation runs.
    # (support-image-service has its own credential too, generated once per
    # process and never rotated on a timer -- see rotation.py's docstring.)
    TOKEN_ROTATION_INTERVAL_SECONDS = int(
        os.environ.get("TOKEN_ROTATION_INTERVAL_SECONDS", "1800")
    )

    # The internal image-management store (support-image-service). Not
    # directly attacker-reachable (see app/services/rotation.py) -- the
    # deliberate vulnerability that lands files here is reached via
    # app/services/catalog_photos.py instead.
    UPLOAD_DIR = str(BASE_DIR / os.environ.get("UPLOAD_DIR", "uploads/images"))

    # Legitimate, admin-only product photo storage -- deliberately a
    # separate top-level directory from UPLOAD_DIR above, not a sibling
    # inside uploads/, so the admin-upload pipeline (properly validated,
    # app/services/product_photos.py) never shares a filesystem path or a
    # database table with UPLOAD_DIR, even though catalog-sync product
    # photos (app/services/catalog_photos.py, weakly validated) end up
    # copied into both.
    PRODUCT_PHOTO_DIR = str(BASE_DIR / os.environ.get("PRODUCT_PHOTO_DIR", "media/product_photos"))

    # Customer ticket-photo attachments (app/services/ticket_photos.py) --
    # same secure, sniff-then-store pattern as PRODUCT_PHOTO_DIR above, its
    # own separate directory for the same reason.
    TICKET_PHOTO_DIR = str(BASE_DIR / os.environ.get("TICKET_PHOTO_DIR", "media/ticket_photos"))

    LOG_DIR = str(BASE_DIR / os.environ.get("LOG_DIR", "logs"))


config = Config()
