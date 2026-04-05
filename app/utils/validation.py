import ipaddress
import re
from urllib.parse import urlparse

from email_validator import EmailNotValidError, validate_email

_LABEL_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$")

_BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "broadcasthost",
    "0.0.0.0",
}

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private_ip(host: str) -> bool:
    try:
        addr = ipaddress.ip_address(host)
        return any(addr in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        return False


def _validate_email(raw: str) -> str | None:
    """Return an error string or None if valid."""
    try:
        validate_email(raw, check_deliverability=False)
        return None
    except EmailNotValidError as exc:
        return str(exc)


def _validate_original_url(url: str) -> str | None:
    """Return an error string or None if valid."""
    if len(url) > 2048:
        return "URL must not exceed 2048 characters"

    if any(c < "\x20" or c == "\x7f" for c in url):
        return "URL contains invalid characters"

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        return "URL must start with http:// or https://"

    if not parsed.netloc or parsed.netloc != parsed.netloc.strip():
        return "URL has an invalid or missing host"

    if parsed.username or parsed.password:
        return "URL must not contain credentials"

    try:
        port = parsed.port
    except ValueError:
        return "URL has an invalid port"

    raw_netloc = parsed.netloc.split("@")[-1]
    if ":" in raw_netloc and port is None:
        return "URL has an invalid port"
    if port is not None and not (0 < port <= 65535):
        return "URL port is out of range"

    hostname = parsed.hostname
    if not hostname:
        return "URL has an invalid or missing host"

    if hostname in _BLOCKED_HOSTS or hostname.endswith(".local"):
        return "URL references a reserved or private host"

    if _is_private_ip(hostname):
        return "URL references a private or loopback IP address"

    if len(hostname) > 253:
        return "URL hostname is too long"

    labels = hostname.rstrip(".").split(".")
    if len(labels) < 2:
        return "URL hostname must include a domain and TLD"

    for label in labels:
        if not label:
            return "URL hostname contains an empty label"
        if len(label) > 63:
            return "URL hostname label exceeds 63 characters"
        if not _LABEL_RE.match(label):
            return "URL hostname contains invalid characters"

    tld = labels[-1]
    if not tld.isalpha() or len(tld) < 2:
        return "URL has an invalid top-level domain"

    return None


def validate_user_create(data):
    """Return a dict of field-level errors, or {"error": msg} for structural problems."""
    if data is None or not isinstance(data, dict):
        return {"error": "Request body must be a JSON object"}

    errors = {}

    if "username" not in data:
        errors["username"] = "Username is required"
    elif not isinstance(data["username"], str) or not data["username"].strip():
        errors["username"] = "Username must be a non-empty string"

    if "email" not in data:
        errors["email"] = "Email is required"
    elif not isinstance(data["email"], str):
        errors["email"] = "Email must be a valid email address"
    else:
        email_error = _validate_email(data["email"])
        if email_error:
            errors["email"] = email_error

    return errors


def validate_user_update(data):
    if data is None or not isinstance(data, dict):
        return {"error": "Request body must be a JSON object"}

    errors = {}

    if "username" in data:
        if not isinstance(data["username"], str) or not data["username"].strip():
            errors["username"] = "Username must be a non-empty string"

    if "email" in data:
        if not isinstance(data["email"], str):
            errors["email"] = "Email must be a valid email address"
        else:
            email_error = _validate_email(data["email"])
            if email_error:
                errors["email"] = email_error

    return errors


def validate_url_create(data):
    if data is None or not isinstance(data, dict):
        return {"error": "Request body must be a JSON object"}

    errors = {}

    if "user_id" not in data:
        errors["user_id"] = "user_id is required"
    elif not isinstance(data["user_id"], int):
        errors["user_id"] = "user_id must be an integer"

    if "original_url" not in data:
        errors["original_url"] = "original_url is required"
    elif not isinstance(data["original_url"], str) or not data["original_url"].strip():
        errors["original_url"] = "original_url must be a non-empty string"
    else:
        url_error = _validate_original_url(data["original_url"].strip())
        if url_error:
            errors["original_url"] = url_error

    if "title" not in data:
        errors["title"] = "title is required"
    elif not isinstance(data["title"], str):
        errors["title"] = "title must be a string"

    return errors


def validate_url_update(data):
    if data is None or not isinstance(data, dict):
        return {"error": "Request body must be a JSON object"}

    errors = {}

    if "title" in data and not isinstance(data["title"], str):
        errors["title"] = "title must be a string"

    if "is_active" in data and not isinstance(data["is_active"], bool):
        errors["is_active"] = "is_active must be a boolean"

    return errors
