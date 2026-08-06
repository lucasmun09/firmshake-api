from services.image_storage import build_storage_key, read_image_bytes, save_image_bytes


def test_build_storage_key_uses_owner_and_image_id():
    image_id = "abc" * 8
    key = build_storage_key("user-123", image_id, "jpg")
    assert key == f"listing-images/user-123/{image_id}.jpg"


def test_local_save_and_read_round_trip(app, tmp_path):
    storage_dir = tmp_path / "images"
    storage_dir.mkdir(exist_ok=True)
    app.config["STORAGE_DIR"] = storage_dir
    app.config["GCS_BUCKET"] = ""

    payload = b"\xff\xd8\xfftest-bytes"

    with app.app_context():
        key = build_storage_key("seller-1", "img-1", "jpg")
        save_image_bytes(key, payload, "image/jpeg")
        assert read_image_bytes(key) == payload
