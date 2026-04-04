from dotenv import load_dotenv
from flask import Flask, jsonify

from app.database import init_db, create_tables
from app.routes import register_routes


def create_app():
    load_dotenv()

    app = Flask(__name__)

    init_db(app)

    from app import models  # noqa: F401

    create_tables()

    register_routes(app)

    @app.route("/health")
    def health():
        return jsonify(status="ok")

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(error="Not found"), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify(error="Internal server error"), 500

    return app
