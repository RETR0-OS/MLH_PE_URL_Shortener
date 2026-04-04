import datetime
import uuid

from flask import Blueprint, jsonify, redirect, request
from peewee import IntegrityError

from app.database import db

from app.event_writer import log_event
from app.models.url import Url
from app.models.user import User
from app.utils import encode_base62

urls_bp = Blueprint("urls", __name__)


@urls_bp.route("/urls", methods=["GET"])
def list_urls():
    query = Url.select().order_by(Url.id)

    user_id = request.args.get("user_id", type=int)
    if user_id is not None:
        query = query.where(Url.user_id == user_id)

    is_active = request.args.get("is_active")
    if is_active is not None:
        query = query.where(Url.is_active == (is_active.lower() == "true"))

    return jsonify([u.to_dict() for u in query])


@urls_bp.route("/urls/<int:url_id>", methods=["GET"])
def get_url(url_id):
    try:
        url = Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="URL not found"), 404
    return jsonify(url.to_dict())


@urls_bp.route("/urls/<short_code>/redirect", methods=["GET"])
def redirect_short_code(short_code):
    try:
        url = Url.get(Url.short_code == short_code)
    except Url.DoesNotExist:
        return jsonify(error="Short code not found"), 404

    if not url.is_active:
        return jsonify(error="URL is inactive"), 410

    log_event(url.id, url.user_id_id, "redirect",
              short_code=url.short_code, original_url=url.original_url)

    return redirect(url.original_url, code=302)


@urls_bp.route("/urls", methods=["POST"])
def create_url():
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    user_id = data.get("user_id")
    original_url = data.get("original_url")
    title = data.get("title", "")

    if user_id is None or not isinstance(user_id, int):
        return jsonify(error="user_id must be an integer"), 400
    if not isinstance(original_url, str) or not original_url.strip():
        return jsonify(error="original_url must be a non-empty string"), 400

    try:
        User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="User not found"), 404

    now = datetime.datetime.now()
    with db.atomic():
        url = Url.create(
            user_id=user_id,
            short_code=uuid.uuid4().hex[:12],
            original_url=original_url.strip(),
            title=title if isinstance(title, str) else "",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        url.short_code = encode_base62(url.id)
        url.save()

    log_event(url.id, user_id, "created",
              short_code=url.short_code, original_url=url.original_url)

    return jsonify(url.to_dict()), 201


@urls_bp.route("/urls/<int:url_id>", methods=["PUT"])
def update_url(url_id):
    try:
        url = Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="URL not found"), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    if "title" in data:
        url.title = data["title"] if isinstance(data["title"], str) else ""
    if "is_active" in data:
        if not isinstance(data["is_active"], bool):
            return jsonify(error="is_active must be a boolean"), 400
        url.is_active = data["is_active"]
    if "original_url" in data:
        if not isinstance(data["original_url"], str) or not data["original_url"].strip():
            return jsonify(error="original_url must be a non-empty string"), 400
        url.original_url = data["original_url"].strip()

    url.updated_at = datetime.datetime.now()
    url.save()

    log_event(url.id, url.user_id_id, "updated",
              short_code=url.short_code, original_url=url.original_url)

    return jsonify(url.to_dict())


@urls_bp.route("/urls/<int:url_id>", methods=["DELETE"])
def delete_url(url_id):
    try:
        url = Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="URL not found"), 404

    url.delete_instance(recursive=True)
    return "", 204
