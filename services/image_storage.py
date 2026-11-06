from pathlib import Path

from flask import current_app
from google.cloud import storage
from werkzeug.utils import secure_filename

_client: storage.Client | None = None


def _get_client() -> storage.Client:
    global _client
    if _client is None:
        _client = storage.Client()
    return _client


def uses_gcs() -> bool:
    return bool(current_app.config.get("GCS_BUCKET"))


def _bucket_name() -> str | None:
    bucket = current_app.config.get("GCS_BUCKET")
    return bucket if bucket else None


def build_storage_key(owner_id: str, image_id: str, extension: str) -> str:
    safe_owner = secure_filename(owner_id)
    safe_ext = secure_filename(extension).lstrip(".") or "jpg"
    return f"listing-images/{safe_owner}/{image_id}.{safe_ext}"


def save_image_bytes(storage_key: str, data: bytes, content_type: str) -> None:
    bucket_name = _bucket_name()
    if bucket_name:
        bucket = _get_client().bucket(bucket_name)
        blob = bucket.blob(storage_key)
        blob.cache_control = "private, max-age=0, no-transform"
        blob.upload_from_string(data, content_type=content_type)
        return

    storage_dir: Path = current_app.config["STORAGE_DIR"]
    storage_dir.mkdir(parents=True, exist_ok=True)
    safe_key = secure_filename(storage_key.replace("/", "__"))
    (storage_dir / safe_key).write_bytes(data)


def read_image_bytes(storage_key: str) -> bytes:
    bucket_name = _bucket_name()
    if bucket_name:
        bucket = _get_client().bucket(bucket_name)
        blob = bucket.blob(storage_key)
        if not blob.exists():
            raise FileNotFoundError(storage_key)
        return blob.download_as_bytes()

    storage_dir: Path = current_app.config["STORAGE_DIR"]
    safe_key = secure_filename(storage_key.replace("/", "__"))
    path = storage_dir / safe_key
    if not path.is_file():
        raise FileNotFoundError(storage_key)
    return path.read_bytes()


def image_exists(storage_key: str) -> bool:
    bucket_name = _bucket_name()
    if bucket_name:
        bucket = _get_client().bucket(bucket_name)
        return bucket.blob(storage_key).exists()

    storage_dir: Path = current_app.config["STORAGE_DIR"]
    safe_key = secure_filename(storage_key.replace("/", "__"))
    return (storage_dir / safe_key).is_file()
