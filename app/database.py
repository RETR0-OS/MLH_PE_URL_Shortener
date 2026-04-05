import datetime

from peewee import DatabaseProxy, Model
from playhouse.pool import PooledPostgresqlDatabase

from app.utils.secrets import read_secret

db = DatabaseProxy()


def utcnow():
    """Return a timezone-naive UTC datetime."""
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


class BaseModel(Model):
    class Meta:
        database = db


def _create_database(max_connections=20):
    return PooledPostgresqlDatabase(
        read_secret("database_name", "hackathon_db"),
        host=read_secret("database_host", "localhost"),
        port=int(read_secret("database_port", "5432")),
        user=read_secret("database_user", "postgres"),
        password=read_secret("database_password", "postgres"),
        max_connections=max_connections,
        stale_timeout=300,
        timeout=10,
        # Keep TCP connections alive through Docker NAT (which drops idle
        # connections after ~600s). Start probing after 60s of idle,
        # retry every 10s, give up after 5 failures.
        keepalives=1,
        keepalives_idle=60,
        keepalives_interval=10,
        keepalives_count=5,
    )


def init_db(app):
    database = _create_database()
    db.initialize(database)

    @app.before_request
    def _db_connect():
        from flask import request

        if request.path == "/health":
            return

        from app.middleware import checkpoint

        db.connect(reuse_if_open=True)
        checkpoint("db_connect")

    @app.teardown_appcontext
    def _db_close(exc):
        if not db.is_closed():
            db.close()


def init_db_standalone():
    """Initialise database outside of a Flask request cycle (scripts, CLI)."""
    database = _create_database(max_connections=4)
    db.initialize(database)
