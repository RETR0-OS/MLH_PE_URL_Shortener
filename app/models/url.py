import datetime

from app.database import BaseModel
from app.models.user import User
from peewee import (
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKeyField,
    TextField,
)


class Url(BaseModel):
    user_id = ForeignKeyField(User, backref="urls", column_name="user_id", on_delete="CASCADE")
    short_code = CharField(unique=True, max_length=20)
    original_url = TextField()
    title = CharField(max_length=500, default="")
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "urls"
        indexes = (
            (("user_id",), False),
            (("is_active",), False),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id_id,
            "short_code": self.short_code,
            "original_url": self.original_url,
            "title": self.title,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime.datetime) else str(self.created_at),
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime.datetime) else str(self.updated_at),
        }
