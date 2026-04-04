import secrets
import string

BASE62 = string.digits + string.ascii_letters


def generate_short_code(length=6):
    """Return a cryptographically random Base62 string."""
    return "".join(secrets.choice(BASE62) for _ in range(length))
