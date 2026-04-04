import datetime

from peewee import AutoField, CharField, DateTimeField

from app.database import BaseModel


def _utcnow():
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


class User(BaseModel):
    id = AutoField()
    username = CharField(unique=True, max_length=150)
    email = CharField(unique=True, max_length=255)
    created_at = DateTimeField(default=_utcnow)

    class Meta:
        table_name = "users"

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
