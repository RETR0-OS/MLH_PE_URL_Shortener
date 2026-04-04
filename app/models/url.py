import datetime

from peewee import (
    AutoField,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKeyField,
    TextField,
)

from app.database import BaseModel
from app.models.user import User


def _utcnow():
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


class Url(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, backref="urls", column_name="user_id")
    short_code = CharField(unique=True, max_length=20)
    original_url = TextField()
    title = CharField(max_length=500)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=_utcnow)
    updated_at = DateTimeField(default=_utcnow)

    class Meta:
        table_name = "urls"

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "short_code": self.short_code,
            "original_url": self.original_url,
            "title": self.title,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
