from peewee import AutoField, CharField, DateTimeField, ForeignKeyField
from playhouse.postgres_ext import BinaryJSONField

from app.database import BaseModel, utcnow
from app.models.url import Url
from app.models.user import User


class Event(BaseModel):
    id = AutoField()
    url = ForeignKeyField(Url, backref="events", column_name="url_id", null=True)
    user = ForeignKeyField(
        User, backref="user_events", column_name="user_id", null=True
    )
    event_type = CharField(max_length=50)
    timestamp = DateTimeField(default=utcnow)
    details = BinaryJSONField(default=dict)

    class Meta:
        table_name = "events"

    def to_dict(self):
        return {
            "id": self.id,
            "url_id": self.url_id,
            "user_id": self.user_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "details": self.details,
        }
