import logging

from dotenv import load_dotenv
from flask import Flask, jsonify, send_from_directory
from prometheus_flask_exporter import PrometheusMetrics

from app.database import db, init_db
from app.logging_config import setup_logging
from app.middleware import register_middleware

logger = logging.getLogger(__name__)
metrics = PrometheusMetrics.for_app_factory()


def _create_indexes():
    """Create performance indexes that Peewee doesn't auto-generate."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_urls_user_id ON urls (user_id)",
        "CREATE INDEX IF NOT EXISTS idx_urls_short_code ON urls (short_code)",
        "CREATE INDEX IF NOT EXISTS idx_urls_is_active ON urls (is_active)",
        "CREATE INDEX IF NOT EXISTS idx_urls_user_id_is_active ON urls (user_id, is_active)",
        "CREATE INDEX IF NOT EXISTS idx_events_url_id ON events (url_id)",
        "CREATE INDEX IF NOT EXISTS idx_events_user_id ON events (user_id)",
        "CREATE INDEX IF NOT EXISTS idx_events_event_type ON events (event_type)",
        "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events (timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_events_url_id_event_type ON events (url_id, event_type)",
    ]
    for stmt in indexes:
        try:
            db.execute_sql(stmt)
        except Exception:
            pass


def create_app():
    load_dotenv()
    setup_logging()

    app = Flask(__name__, static_folder="static")

    register_middleware(app)
    init_db(app)
    metrics.init_app(app)

    from app.models.event import Event
    from app.models.url import Url
    from app.models.user import User

    with db.connection_context():
        try:
            db.create_tables([User, Url, Event], safe=True)
        except Exception:
            logger.info("Tables already exist (concurrent worker race), continuing")
        _create_indexes()

    from app.routes import register_routes
    from app.utils.cache import warm_up

    register_routes(app)
    warm_up()

    from app.auth import register_api_key_auth

    register_api_key_auth(app)

    from app.tracing import init_tracing

    init_tracing(app)

    # --- Swagger UI at /docs ---
    try:
        from flask_swagger_ui import get_swaggerui_blueprint

        SWAGGER_URL = "/docs"
        API_URL = "/apispec.json"
        swagger_bp = get_swaggerui_blueprint(
            SWAGGER_URL, API_URL, config={"app_name": "MLH URL Shortener"}
        )
        app.register_blueprint(swagger_bp, url_prefix=SWAGGER_URL)
    except ImportError:
        logger.info("flask-swagger-ui not installed – Swagger docs disabled")

    @app.route("/apispec.json")
    @metrics.do_not_track()
    def apispec():
        return send_from_directory(app.static_folder, "openapi.json")

    # --- Health endpoints ---
    @app.route("/health")
    @metrics.do_not_track()
    def health():
        return jsonify(status="ok")

    @app.route("/health/ready")
    @metrics.do_not_track()
    def health_ready():
        try:
            db.execute_sql("SELECT 1")
            return jsonify(status="ok")
        except Exception:
            return jsonify(status="unavailable"), 503

    # --- Error handlers ---
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify(error="Bad request"), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify(error="Unauthorized"), 401

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(error="Not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify(error="Method not allowed"), 405

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify(error="Internal server error"), 500

    return app
