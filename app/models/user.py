import datetime

from app.database import BaseModel
from peewee import CharField, DateTimeField


class User(BaseModel):
    username = CharField(unique=True, max_length=150)
    email = CharField(unique=True, max_length=255)
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "users"

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime.datetime) else str(self.created_at),
        }
