import re

EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


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
    elif not isinstance(data["email"], str) or not EMAIL_RE.match(data["email"]):
        errors["email"] = "Email must be a valid email address"

    return errors


def validate_user_update(data):
    if data is None or not isinstance(data, dict):
        return {"error": "Request body must be a JSON object"}

    errors = {}

    if "username" in data:
        if not isinstance(data["username"], str) or not data["username"].strip():
            errors["username"] = "Username must be a non-empty string"

    if "email" in data:
        if not isinstance(data["email"], str) or not EMAIL_RE.match(data["email"]):
            errors["email"] = "Email must be a valid email address"

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
