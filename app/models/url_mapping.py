import datetime
from peewee import CharField, DateTimeField, IntegerField, ForeignKeyField
from app.database import BaseModel

class URLMapping(BaseModel):
    """Model representing a URL mapping from a short code to a long URL."""
    
    short_code = CharField(unique=True, max_length=100)
    long_url = CharField(max_length=8000)
    created_at = DateTimeField(default=datetime.datetime.now)
    access_count = IntegerField(default=0)

    owner = For