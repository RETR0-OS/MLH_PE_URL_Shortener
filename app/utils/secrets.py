import os
from pathlib import Path


def read_secret(name, default=None):
    """Read a Docker secret, falling back to an environment variable."""
    secret_path = Path(f"/run/secrets/{name}")
    if secret_path.exists():
        return secret_path.read_text().strip()
    return os.environ.get(name.upper(), default)
