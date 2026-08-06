import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage" / "images"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

HOST = os.getenv("FLASK_HOST", "0.0.0.0")
PORT = int(os.getenv("PORT") or os.getenv("FLASK_PORT", "5001"))
DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
MAX_CONTENT_LENGTH = int(1.5 * 1024 * 1024)  # 1.5 MB
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

_DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173,"
    "http://localhost:5174,"
    "http://localhost:8100,"
    "capacitor://localhost,"
    "ionic://localhost"
)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", _DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
]

FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "firmshake-dev")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

GCS_BUCKET = os.getenv("GCS_BUCKET", "").strip()

IMAGE_UPLOAD_RATE_LIMIT = int(os.getenv("IMAGE_UPLOAD_RATE_LIMIT", "20"))
IMAGE_UPLOAD_RATE_WINDOW_SECONDS = int(os.getenv("IMAGE_UPLOAD_RATE_WINDOW_SECONDS", "3600"))

# Global API rate limits (in-memory per instance; use Redis/Memorystore for distributed limits)
API_RATE_LIMIT_IP = int(os.getenv("API_RATE_LIMIT_IP", "300"))
API_RATE_LIMIT_IP_WINDOW_SECONDS = int(os.getenv("API_RATE_LIMIT_IP_WINDOW_SECONDS", "60"))
API_RATE_LIMIT_UID = int(os.getenv("API_RATE_LIMIT_UID", "120"))
API_RATE_LIMIT_UID_WINDOW_SECONDS = int(os.getenv("API_RATE_LIMIT_UID_WINDOW_SECONDS", "60"))

# Average city driving speed for ETA fallback (~25 mph)
ETA_SPEED_MPH = float(os.getenv("ETA_SPEED_MPH", "25"))
ARRIVAL_RADIUS_METERS = int(os.getenv("ARRIVAL_RADIUS_METERS", "100"))
