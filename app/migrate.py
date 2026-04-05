"""Database migration runner using peewee_migrate.

Usage:
    python -m app.migrate          # run all pending migrations
    python -m app.migrate create   # create a new empty migration
"""

import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_router():
    from peewee_migrate import Router
    from app.database import db, init_db_standalone

    init_db_standalone()
    return Router(db.obj, migrate_dir="migrations")


def main():
    router = get_router()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd == "run":
        logger.info("Running pending migrations ...")
        router.run()
        logger.info("Migrations complete.")
    elif cmd == "create":
        name = sys.argv[2] if len(sys.argv) > 2 else "auto"
        logger.info("Creating migration '%s' ...", name)
        router.create(name, auto="app.models")
        logger.info("Migration created.")
    elif cmd == "rollback":
        logger.info("Rolling back last migration ...")
        router.rollback()
        logger.info("Rollback complete.")
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python -m app.migrate [run|create|rollback]")
        sys.exit(1)


if __name__ == "__main__":
    main()
