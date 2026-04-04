import os

import pytest

os.environ.setdefault("DATABASE_NAME", "hackathon_db_test")
os.environ.setdefault("DATABASE_HOST", "localhost")
os.environ.setdefault("DATABASE_PORT", "5432")
os.environ.setdefault("DATABASE_USER", os.environ.get("USER", "postgres"))
os.environ.setdefault("DATABASE_PASSWORD", "")

from app import create_app  # noqa: E402
from app.database import db  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.url import Url  # noqa: E402
from app.models.user import User  # noqa: E402

MODELS = [User, Url, Event]


@pytest.fixture(scope="session")
def app():
    application = create_app()
    application.config["TESTING"] = True
    yield application


@pytest.fixture(autouse=True)
def _clean_tables():
    """Truncate all tables before each test for full isolation."""
    with db.connection_context():
        db.execute_sql(
            'TRUNCATE TABLE "events", "urls", "users" RESTART IDENTITY CASCADE'
        )
    yield


@pytest.fixture()
def client(app):
    return app.test_client()
