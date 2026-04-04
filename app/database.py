import os
from pathlib import Path

from peewee import DatabaseProxy, Model
from playhouse.pool import PooledPostgresqlDatabase

db = DatabaseProxy()


class BaseModel(Model):
    class Meta:
        database = db


def _read_secret(name, default=None):
    """Read a Docker secret, falling back to an environment variable."""
    secret_path = Path(f"/run/secrets/{name}")
    if secret_path.exists():
        return secret_path.read_text().strip()
    return os.environ.get(name.upper(), default)


def _create_database(max_connections=20):
    return PooledPostgresqlDatabase(
        _read_secret("database_name", "hackathon_db"),
        host=_read_secret("database_host", "localhost"),
        port=int(_read_secret("database_port", "5432")),
        user=_read_secret("database_user", "postgres"),
        password=_read_secret("database_password", "postgres"),
        max_connections=max_connections,
        stale_timeout=300,
        timeout=10,
    )


def init_db(app):
    database = _create_database()
    db.initialize(database)

    @app.before_request
    def _db_connect():
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
