"""Versioned BFF routes under /api/v1."""

from flask import Blueprint

from routes.v1.agreements import agreements_bp, webhooks_bp
from routes.v1.blocks import blocks_bp
from routes.v1.browse import browse_bp
from routes.v1.catalog import catalog_bp
from routes.v1.communities import communities_bp
from routes.v1.inbox import inbox_bp
from routes.v1.listings import listings_bp
from routes.v1.users import users_bp

v1_bp = Blueprint("v1", __name__, url_prefix="/api/v1")
v1_bp.register_blueprint(inbox_bp, url_prefix="/inbox")
v1_bp.register_blueprint(listings_bp, url_prefix="/listings")
v1_bp.register_blueprint(agreements_bp, url_prefix="/agreements")
v1_bp.register_blueprint(webhooks_bp, url_prefix="/webhooks")
v1_bp.register_blueprint(users_bp, url_prefix="/users")
v1_bp.register_blueprint(blocks_bp, url_prefix="/users/me/blocks")
v1_bp.register_blueprint(communities_bp, url_prefix="/communities")
v1_bp.register_blueprint(catalog_bp)
v1_bp.register_blueprint(browse_bp, url_prefix="/browse")

__all__ = ["v1_bp"]
