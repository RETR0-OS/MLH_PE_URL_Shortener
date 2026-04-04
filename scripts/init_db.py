from dotenv import load_dotenv

load_dotenv()

from app.database import db, init_db_standalone
from app.models.event import Event
from app.models.url import Url
from app.models.user import User

init_db_standalone()

with db.connection_context():
    db.create_tables([User, Url, Event], safe=True)
    db.execute_sql(
        "ALTER TABLE events ALTER COLUMN url_id DROP NOT NULL,"
        " ALTER COLUMN user_id DROP NOT NULL"
    )

print("Database initialized successfully.")
