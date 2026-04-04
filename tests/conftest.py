import pytest
from peewee import SqliteDatabase

import app.database as _db_module
from app.database import db
from app.models import User, Url, Event

MODELS = [User, Url, Event]


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    test_db = SqliteDatabase(db_path, pragmas={
        "journal_mode": "wal",
        "foreign_keys": 1,
    })

    _db_module._testing = False
    db.initialize(test_db)
    test_db.bind(MODELS)
    test_db.connect()
    test_db.create_tables(MODELS)
    yield
    from app.event_writer import flush_pending
    flush_pending()
    test_db.drop_tables(MODELS)
    test_db.close()


@pytest.fixture()
def app(setup_db):
    from app import create_app

    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture()
def client(app):
    return app.test_client()
