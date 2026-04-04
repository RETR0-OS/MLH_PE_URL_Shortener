"""Optional API-key authentication middleware.

When API_KEY is set (non-empty), every request must include a matching
X-API-Key header.  Health-check endpoints are always exempt.
"""
import os
import logging

from flask import jsonify, request

logger = logging.getLogger(__name__)

EXEMPT_PATHS = frozenset({"/health", "/health/ready", "/nginx-status", "/docs", "/docs/", "/apispec.json"})


def register_api_key_auth(app):
    api_key = os.environ.get("API_KEY", "").strip()
    if not api_key:
        logger.info("API_KEY not set – API-key auth disabled")
        return

    logger.info("API-key authentication enabled")

    @app.before_request
    def _check_api_key():
        if request.path in EXEMPT_PATHS or request.path.startswith("/docs/"):
            return None
        if request.method == "OPTIONS":
            return None
        provided = request.headers.get("X-API-Key", "")
        if provided != api_key:
            return jsonify(error="Unauthorized – invalid or missing API key"), 401
