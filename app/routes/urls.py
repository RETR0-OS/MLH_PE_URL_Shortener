import datetime

from flask import Blueprint, jsonify, request
from peewee import IntegrityError

from app.database import db
from app.models.event import Event
from app.models.url import Url
from app.models.user import User
from app.utils.cache import cache_delete, cache_delete_pattern, cache_get, cache_set
from app.utils.shortcode import generate_short_code
from app.utils.validation import validate_url_create, validate_url_update

urls_bp = Blueprint("urls", __name__)


def _utcnow():
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


@urls_bp.route("/urls", methods=["GET"])
def list_urls():
    query = Url.select().order_by(Url.id)

    user_id = request.args.get("user_id", type=int)
    if user_id is not None:
        query = query.where(Url.user == user_id)

    return jsonify([u.to_dict() for u in query])


@urls_bp.route("/urls", methods=["POST"])
def create_url():
    data = request.get_json(silent=True)
    errors = validate_url_create(data)
    if "error" in errors:
        return jsonify(errors), 400
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422

    try:
        User.get_by_id(data["user_id"])
    except User.DoesNotExist:
        return jsonify(error=f"User {data['user_id']} not found"), 400

    short_code = None
    for _ in range(10):
        candidate = generate_short_code()
        if not Url.select().where(Url.short_code == candidate).exists():
            short_code = candidate
            break
    if short_code is None:
        return jsonify(error="Failed to generate unique short code"), 500

    now = _utcnow()
    try:
        with db.atomic():
            url = Url.create(
                user=data["user_id"],
                short_code=short_code,
                original_url=data["original_url"],
                title=data["title"],
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            Event.create(
                url=url.id,
                user=data["user_id"],
                event_type="created",
                timestamp=now,
                details={
                    "short_code": short_code,
                    "original_url": data["original_url"],
                },
            )
    except IntegrityError as exc:
        return jsonify({"error": str(exc)}), 422

    cache_delete_pattern("urls:user:*")
    return jsonify(url.to_dict()), 201


@urls_bp.route("/urls/<int:url_id>", methods=["GET"])
def get_url(url_id):
    cached = cache_get(f"url:{url_id}")
    if cached is not None:
        return jsonify(cached)

    try:
        url = Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="URL not found"), 404

    data = url.to_dict()
    cache_set(f"url:{url_id}", data, ttl=300)
    return jsonify(data)


@urls_bp.route("/urls/<int:url_id>", methods=["PUT"])
def update_url(url_id):
    try:
        url = Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="URL not found"), 404

    data = request.get_json(silent=True)
    errors = validate_url_update(data)
    if "error" in errors:
        return jsonify(errors), 400
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    try:
        with db.atomic():
            if "title" in data:
                url.title = data["title"]
            if "is_active" in data:
                url.is_active = data["is_active"]
            url.updated_at = _utcnow()
            url.save()
    except IntegrityError as exc:
        return jsonify({"error": str(exc)}), 422

    cache_delete(f"url:{url_id}")
    cache_delete_pattern("urls:user:*")
    return jsonify(url.to_dict())
