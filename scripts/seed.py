#!/usr/bin/env python
"""Seed the database with CSV data from the data/ directory."""
import csv
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app.database import db, init_db_standalone  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.url import Url  # noqa: E402
from app.models.user import User  # noqa: E402

BATCH_SIZE = 100


def _parse_dt(value):
    return datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _reset_pk_sequence(model):
    table = model._meta.table_name
    db.execute_sql(
        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
        f'COALESCE((SELECT MAX(id) FROM "{table}"), 0))'
    )


def seed_users(path="data/users.csv"):
    with open(path) as f:
        rows = [
            {
                "id": int(r["id"]),
                "username": r["username"],
                "email": r["email"],
                "created_at": _parse_dt(r["created_at"]),
            }
            for r in csv.DictReader(f)
        ]
    with db.atomic():
        for i in range(0, len(rows), BATCH_SIZE):
            User.insert_many(rows[i : i + BATCH_SIZE]).execute()
    _reset_pk_sequence(User)
    return len(rows)


def seed_urls(path="data/urls.csv"):
    with open(path) as f:
        rows = [
            {
                "id": int(r["id"]),
                "user_id": int(r["user_id"]),
                "short_code": r["short_code"],
                "original_url": r["original_url"],
                "title": r["title"],
                "is_active": r["is_active"] == "True",
                "created_at": _parse_dt(r["created_at"]),
                "updated_at": _parse_dt(r["updated_at"]),
            }
            for r in csv.DictReader(f)
        ]
    with db.atomic():
        for i in range(0, len(rows), BATCH_SIZE):
            Url.insert_many(rows[i : i + BATCH_SIZE]).execute()
    _reset_pk_sequence(Url)
    return len(rows)


def seed_events(path="data/events.csv"):
    with open(path) as f:
        rows = [
            {
                "id": int(r["id"]),
                "url_id": int(r["url_id"]),
                "user_id": int(r["user_id"]),
                "event_type": r["event_type"],
                "timestamp": _parse_dt(r["timestamp"]),
                "details": json.loads(r["details"]),
            }
            for r in csv.DictReader(f)
        ]
    with db.atomic():
        for i in range(0, len(rows), BATCH_SIZE):
            Event.insert_many(rows[i : i + BATCH_SIZE]).execute()
    _reset_pk_sequence(Event)
    return len(rows)


def main():
    init_db_standalone()
    db.connect()
    db.create_tables([User, Url, Event], safe=True)

    print(f"Seeded {seed_users()} users")
    print(f"Seeded {seed_urls()} urls")
    print(f"Seeded {seed_events()} events")
    print("Done!")

    db.close()


if __name__ == "__main__":
    main()
