import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage" / "images"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

HOST = os.getenv("FLASK_HOST", "0.0.0.0")
PORT = int(os.getenv("FLASK_PORT", "5001"))
DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
