import datetime

from flask import Blueprint, jsonify, redirect, request
from peewee import IntegrityError

from app.database import db
from app.event_writer import log_event
from app.middleware import checkpoint
from app.models.url import Url
from app.models.user import User
from app.utils.cache import cache_delete, cache_get, cache_set
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

    is_active = request.args.get("is_active")
    if is_active is not None:
        query = query.where(Url.is_active == (is_active.lower() == "true"))

    checkpoint("query_build")
    result = [u.to_dict() for u in query]
    checkpoint("db_query_and_serialize")
    return jsonify(result)


@urls_bp.route("/urls", methods=["POST"])
def create_url():
    data = request.get_json(silent=True)
    errors = validate_url_create(data)
    if "error" in errors:
        return jsonify(errors), 400
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422
    checkpoint("validation")

    try:
        User.get_by_id(data["user_id"])
    except User.DoesNotExist:
        return jsonify(error=f"User {data['user_id']} not found"), 400
    checkpoint("user_lookup")

    now = _utcnow()
    for attempt in range(3):
        short_code = generate_short_code()
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
            checkpoint("url_insert")
            break
        except IntegrityError:
            if attempt == 2:
                return jsonify(error="Failed to generate unique short code"), 500

    log_event(url.id, data["user_id"], "created", {
        "short_code": short_code,
        "original_url": data["original_url"],
    })
    checkpoint("event_queued")

    resp = jsonify(url.to_dict())
    checkpoint("serialize")
    return resp, 201


@urls_bp.route("/urls/<int:url_id>", methods=["GET"])
def get_url(url_id):
    cached = cache_get(f"url:{url_id}")
    checkpoint("cache_get")
    if cached is not None:
        return jsonify(cached)

    try:
        url = Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="URL not found"), 404
    checkpoint("db_read")

    data = url.to_dict()
    cache_set(f"url:{url_id}", data, ttl=300)
    checkpoint("cache_set")
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
    return jsonify(url.to_dict())


@urls_bp.route("/urls/<short_code>/redirect", methods=["GET"])
def redirect_short_code(short_code):
    try:
        url = Url.get(Url.short_code == short_code)
    except Url.DoesNotExist:
        return jsonify(error="Not found"), 404

    if not url.is_active:
        return jsonify(error="URL is deactivated"), 410

    log_event(url.id, url.user_id, "redirect", {"short_code": short_code})
    return redirect(url.original_url, code=302)


@urls_bp.route("/urls/<int:url_id>", methods=["DELETE"])
def delete_url(url_id):
    try:
        url = Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="URL not found"), 404

    url.delete_instance(recursive=True)
    cache_delete(f"url:{url_id}")
    return "", 204
