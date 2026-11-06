ALLOWED_IMAGE_TYPES = {
    "jpeg": (b"\xff\xd8\xff", "image/jpeg"),
    "png": (b"\x89PNG\r\n\x1a\n", "image/png"),
    "gif": (b"GIF87a", "image/gif"),
    "gif89a": (b"GIF89a", "image/gif"),
    "webp": (b"RIFF", "image/webp"),
}


def detect_image_content_type(data: bytes) -> str | None:
    if len(data) < 12:
        return None

    if data.startswith(ALLOWED_IMAGE_TYPES["jpeg"][0]):
        return "image/jpeg"
    if data.startswith(ALLOWED_IMAGE_TYPES["png"][0]):
        return "image/png"
    if data.startswith(ALLOWED_IMAGE_TYPES["gif"][0]) or data.startswith(
        ALLOWED_IMAGE_TYPES["gif89a"][0]
    ):
        return "image/gif"
    if data.startswith(ALLOWED_IMAGE_TYPES["webp"][0]) and data[8:12] == b"WEBP":
        return "image/webp"

    return None
