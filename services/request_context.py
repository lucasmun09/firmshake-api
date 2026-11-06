import logging
import uuid

from flask import Flask, g, request

logger = logging.getLogger("firmshake.request")


def init_request_context(app: Flask) -> None:
    @app.before_request
    def assign_request_id() -> None:
        incoming = request.headers.get("X-Request-Id", "").strip()
        g.request_id = incoming or uuid.uuid4().hex
        g.authenticated_uid = None

    @app.after_request
    def log_request(response):
        uid = getattr(g, "authenticated_uid", None)
        logger.info(
            "request completed",
            extra={
                "request_id": getattr(g, "request_id", None),
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "uid": uid,
                "remote_addr": request.remote_addr,
            },
        )
        response.headers["X-Request-Id"] = getattr(g, "request_id", "")
        return response
