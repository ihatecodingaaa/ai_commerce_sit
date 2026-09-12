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
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
    OLLAMA_TIMEOUT_SECONDS = int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "60"))

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

    LOG_DIR = str(BASE_DIR / os.environ.get("LOG_DIR", "logs"))


config = Config()
