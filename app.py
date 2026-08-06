import logging

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from config import (
    CORS_ORIGINS,
    DEBUG,
    GCS_BUCKET,
    HOST,
    MAX_CONTENT_LENGTH,
    PORT,
    STORAGE_DIR,
)
from routes.auth import auth_bp
from routes.controlpanel import controlpanel_bp
from routes.health import health_bp
from routes.images import images_bp
from routes.listings import listings_bp
from routes.v1 import v1_bp
from routes.meetups import meetups_bp
from routes.notifications import notifications_bp
from services.api_middleware import init_api_middleware
from services.request_context import init_request_context


def create_app() -> Flask:
    logging.basicConfig(level=logging.INFO)

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
    app.config["STORAGE_DIR"] = STORAGE_DIR
    app.config["GCS_BUCKET"] = GCS_BUCKET

    CORS(
        app,
        resources={
            r"/api/*": {"origins": CORS_ORIGINS},
            r"/health": {"origins": CORS_ORIGINS},
        },
    )

    init_request_context(app)
    init_api_middleware(app)

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(controlpanel_bp)
    app.register_blueprint(images_bp)
    app.register_blueprint(listings_bp)
    app.register_blueprint(v1_bp)
    app.register_blueprint(meetups_bp)
    app.register_blueprint(notifications_bp)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=DEBUG)
