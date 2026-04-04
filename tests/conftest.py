import app.database as _db_module
import pytest
from peewee import SqliteDatabase

from app.database import db
from app.models import User, Url, Event

TEST_DB = SqliteDatabase(":memory:")
MODELS = [User, Url, Event]


@pytest.fixture(autouse=True)
def setup_db():
    _db_module._testing = True
    db.initialize(TEST_DB)
    TEST_DB.bind(MODELS)
    TEST_DB.connect()
    TEST_DB.create_tables(MODELS)
    yield
    TEST_DB.drop_tables(MODELS)
    TEST_DB.close()
    _db_module._testing = False


@pytest.fixture()
def app(setup_db):
    from app import create_app

    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture()
def client(app):
    return app.test_client()
