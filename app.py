from flask import Flask
from flask_cors import CORS

from config import ALLOWED_EXTENSIONS, DEBUG, HOST, MAX_CONTENT_LENGTH, PORT, STORAGE_DIR
from routes.health import health_bp
from routes.images import images_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
    app.config["STORAGE_DIR"] = STORAGE_DIR
    app.config["ALLOWED_EXTENSIONS"] = ALLOWED_EXTENSIONS

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": [
                    "http://localhost:5173",
                    "http://localhost:8100",
                    "capacitor://localhost",
                    "ionic://localhost",
                ]
            }
        },
    )

    app.register_blueprint(health_bp)
    app.register_blueprint(images_bp)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=DEBUG)
