import datetime
import json

from app.database import BaseModel
from app.models.url import Url
from app.models.user import User
from peewee import CharField, DateTimeField, ForeignKeyField, TextField


class Event(BaseModel):
    url_id = ForeignKeyField(Url, backref="events", column_name="url_id", on_delete="CASCADE")
    user_id = ForeignKeyField(User, backref="events", column_name="user_id", on_delete="CASCADE")
    event_type = CharField(max_length=50)
    timestamp = DateTimeField(default=datetime.datetime.now)
    details = TextField(default="{}")

    class Meta:
        table_name = "events"
        indexes = (
            (("url_id",), False),
            (("user_id",), False),
            (("event_type",), False),
        )

    def to_dict(self):
        details = self.details
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except (json.JSONDecodeError, TypeError):
                details = {}
        return {
            "id": self.id,
            "url_id": self.url_id_id,
            "user_id": self.user_id_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime.datetime) else str(self.timestamp),
            "details": details,
        }
