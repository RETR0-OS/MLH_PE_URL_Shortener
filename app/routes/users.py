import csv
import datetime
import io

from flask import Blueprint, jsonify, request
from peewee import IntegrityError

from app.database import db
from app.middleware import checkpoint
from app.models.user import User
from app.utils.validation import validate_user_create, validate_user_update

users_bp = Blueprint("users", __name__)


def _reset_pk_sequence():
    db.execute_sql(
        "SELECT setval(pg_get_serial_sequence('users', 'id'), "
        'COALESCE((SELECT MAX(id) FROM "users"), 0))'
    )


@users_bp.route("/users", methods=["GET"])
def list_users():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = User.select().order_by(User.id).paginate(page, per_page)
    result = [u.to_dict() for u in query]
    checkpoint("db_query_and_serialize")
    return jsonify(result)


@users_bp.route("/users", methods=["POST"])
def create_user():
    data = request.get_json(silent=True)
    errors = validate_user_create(data)
    if "error" in errors:
        return jsonify(errors), 400
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422
    checkpoint("validation")

    try:
        with db.atomic():
            user = User.create(username=data["username"], email=data["email"])
    except IntegrityError as exc:
        return jsonify({"error": str(exc)}), 422
    checkpoint("db_write")

    return jsonify(user.to_dict()), 201


@users_bp.route("/users/bulk", methods=["POST"])
def bulk_load_users():
    if "file" not in request.files:
        return jsonify(error="No file provided"), 400

    file = request.files["file"]
    stream = io.StringIO(file.stream.read().decode("utf-8"))
    reader = csv.DictReader(stream)

    rows = []
    for row in reader:
        rows.append(
            {
                "id": int(row["id"]),
                "username": row["username"],
                "email": row["email"],
                "created_at": datetime.datetime.strptime(
                    row["created_at"], "%Y-%m-%d %H:%M:%S"
                ),
            }
        )

    count = len(rows)
    if rows:
        with db.atomic():
            for i in range(0, len(rows), 100):
                (
                    User.insert_many(rows[i : i + 100])
                    .on_conflict_ignore()
                    .execute()
                )
        _reset_pk_sequence()

    return jsonify(count=count, imported=count)


@users_bp.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    try:
        user = User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="User not found"), 404

    return jsonify(user.to_dict())


@users_bp.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    try:
        user = User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="User not found"), 404

    from app.models.event import Event
    from app.models.url import Url

    with db.atomic():
        user_url_ids = [u.id for u in Url.select(Url.id).where(Url.user == user_id)]
        if user_url_ids:
            Event.update({Event.url: None}).where(Event.url.in_(user_url_ids)).execute()
        Event.update({Event.user: None}).where(Event.user == user_id).execute()
        Url.delete().where(Url.user == user_id).execute()
        user.delete_instance()

    return "", 204

@users_bp.route("/users/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    try:
        user = User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="User not found"), 404

    data = request.get_json(silent=True)
    errors = validate_user_update(data)
    if "error" in errors:
        return jsonify(errors), 400
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    try:
        with db.atomic():
            if "username" in data:
                user.username = data["username"]
            if "email" in data:
                user.email = data["email"]
            user.save()
    except IntegrityError as exc:
        return jsonify({"error": str(exc)}), 422

    return jsonify(user.to_dict())
