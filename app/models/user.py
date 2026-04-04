import datetime
from webob import static
from aiofiles.os import stat
from argon2 import PasswordHasher
from app.database import BaseModel
from peewee import CharField, BooleanField, CharField, DateTimeField, ForeignKeyField, IntegerField

EMAIL_DOMAIN_WHITELIST = {
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
}

class User(BaseModel):
    """Model representing a user of the URL shortener service."""
    
    username = CharField(unique=True, max_length=150)
    email = CharField(unique=True, max_length=255)
    password_hash = CharField(max_length=255)
    created_at = DateTimeField(default=datetime.datetime.now)
    is_active = BooleanField(default=True)
    is_admin = BooleanField(default=False)
    is_superuser = BooleanField(default=False)

    def __str__(self):
        return f"User(username={self.username}, email={self.email})"
    
    def check_password(self, password: str) -> bool:
        """Check if the provided password matches the stored password hash."""
        # In a real implementation, you would use a secure password hashing algorithm
        # like bcrypt or Argon2. This is just a placeholder.
        return self.password_hash == password

    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate the email format."""
        

    

