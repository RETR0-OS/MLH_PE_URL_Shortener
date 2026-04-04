from dotenv import load_dotenv
from flask import Flask, jsonify
from prometheus_flask_exporter import PrometheusMetrics

from app.database import db, init_db
from app.logging_config import setup_logging
from app.middleware import register_middleware

metrics = PrometheusMetrics.for_app_factory()


def create_app():
    load_dotenv()
    setup_logging()

    app = Flask(__name__)

    register_middleware(app)
    init_db(app)
    metrics.init_app(app)

    from app.models.event import Event
    from app.models.url import Url
    from app.models.user import User

    with db.connection_context():
        db.create_tables([User, Url, Event], safe=True)
        db.execute_sql(
            'ALTER TABLE events ALTER COLUMN url_id DROP NOT NULL,'
            ' ALTER COLUMN user_id DROP NOT NULL'
        )

    from app.routes import register_routes
    from app.utils.cache import warm_up

    register_routes(app)
    warm_up()

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
