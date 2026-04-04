"""Unit tests for utilities: validation, short code generation, serialization."""
import datetime

from app.utils.shortcode import generate_short_code
from app.utils.validation import (
    validate_url_create,
    validate_url_update,
    validate_user_create,
    validate_user_update,
)


class TestShortCode:
    def test_length_default(self):
        code = generate_short_code()
        assert len(code) == 6

    def test_length_custom(self):
        code = generate_short_code(length=10)
        assert len(code) == 10

    def test_base62_chars_only(self):
        import string

        allowed = set(string.digits + string.ascii_letters)
        for _ in range(50):
            code = generate_short_code()
            assert all(c in allowed for c in code)

    def test_uniqueness(self):
        codes = {generate_short_code() for _ in range(200)}
        assert len(codes) == 200


class TestTimestampSerialization:
    def test_naive_iso_format(self):
        dt = datetime.datetime(2025, 9, 19, 22, 25, 5)
        assert dt.isoformat() == "2025-09-19T22:25:05"

    def test_no_timezone_suffix(self):
        dt = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        serialized = dt.isoformat()
        assert "Z" not in serialized
        assert "+" not in serialized


class TestValidateUserCreate:
    def test_valid(self):
        assert validate_user_create({"username": "a", "email": "a@b.com"}) == {}

    def test_none_body(self):
        assert "error" in validate_user_create(None)

    def test_missing_username(self):
        errs = validate_user_create({"email": "a@b.com"})
        assert "username" in errs

    def test_missing_email(self):
        errs = validate_user_create({"username": "a"})
        assert "email" in errs

    def test_integer_username(self):
        errs = validate_user_create({"username": 123, "email": "a@b.com"})
        assert "username" in errs

    def test_invalid_email(self):
        errs = validate_user_create({"username": "a", "email": "not-email"})
        assert "email" in errs

    def test_empty_username(self):
        errs = validate_user_create({"username": "  ", "email": "a@b.com"})
        assert "username" in errs


class TestValidateUserUpdate:
    def test_valid_partial(self):
        assert validate_user_update({"username": "x"}) == {}

    def test_none_body(self):
        assert "error" in validate_user_update(None)

    def test_empty_dict(self):
        assert validate_user_update({}) == {}

    def test_integer_username(self):
        errs = validate_user_update({"username": 42})
        assert "username" in errs


class TestValidateUrlCreate:
    def test_valid(self):
        data = {"user_id": 1, "original_url": "https://x.com", "title": "T"}
        assert validate_url_create(data) == {}

    def test_missing_user_id(self):
        errs = validate_url_create({"original_url": "https://x.com", "title": "T"})
        assert "user_id" in errs

    def test_string_user_id(self):
        errs = validate_url_create(
            {"user_id": "abc", "original_url": "https://x.com", "title": "T"}
        )
        assert "user_id" in errs

    def test_missing_original_url(self):
        errs = validate_url_create({"user_id": 1, "title": "T"})
        assert "original_url" in errs

    def test_missing_title(self):
        errs = validate_url_create({"user_id": 1, "original_url": "https://x.com"})
        assert "title" in errs


class TestValidateUrlUpdate:
    def test_valid(self):
        assert validate_url_update({"title": "new", "is_active": False}) == {}

    def test_non_bool_is_active(self):
        errs = validate_url_update({"is_active": "yes"})
        assert "is_active" in errs

    def test_non_string_title(self):
        errs = validate_url_update({"title": 123})
        assert "title" in errs
