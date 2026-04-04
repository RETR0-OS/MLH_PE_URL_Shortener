import os

from peewee import DatabaseProxy, Model
from playhouse.pool import PooledPostgresqlDatabase

db = DatabaseProxy()

_testing = False


class BaseModel(Model):
    class Meta:
        database = db


def init_db(app):
    if not db.obj:
        database = PooledPostgresqlDatabase(
            os.environ.get("DATABASE_NAME", "hackathon_db"),
            host=os.environ.get("DATABASE_HOST", "localhost"),
            port=int(os.environ.get("DATABASE_PORT", 5432)),
            user=os.environ.get("DATABASE_USER", "postgres"),
            password=os.environ.get("DATABASE_PASSWORD", "postgres"),
            max_connections=20,
            stale_timeout=300,
        )
        db.initialize(database)

    @app.before_request
    def _db_connect():
        if not _testing:
            db.connect(reuse_if_open=True)

    @app.teardown_appcontext
    def _db_close(exc):
        if not _testing and not db.is_closed():
            db.close()


def create_tables():
    from app.models import User, Url, Event

    db.connect(reuse_if_open=True)
    db.create_tables([User, Url, Event])
