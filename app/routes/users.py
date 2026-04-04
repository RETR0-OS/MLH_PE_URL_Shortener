import csv
import io
import datetime

from flask import Blueprint, jsonify, request
from peewee import IntegrityError

from app.models.user import User

users_bp = Blueprint("users", __name__)


@users_bp.route("/users", methods=["GET"])
def list_users():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    page = max(1, page)
    per_page = max(1, min(per_page, 100))

    query = User.select().order_by(User.id)
    users = query.paginate(page, per_page)
    return jsonify([u.to_dict() for u in users])


@users_bp.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    try:
        user = User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="User not found"), 404
    return jsonify(user.to_dict())


@users_bp.route("/users", methods=["POST"])
def create_user():
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    username = data.get("username")
    email = data.get("email")

    if not isinstance(username, str) or not username.strip():
        return jsonify(error="username must be a non-empty string"), 400
    if not isinstance(email, str) or not email.strip():
        return jsonify(error="email must be a non-empty string"), 400

    try:
        user = User.create(
            username=username.strip(),
            email=email.strip(),
            created_at=datetime.datetime.now(),
        )
    except IntegrityError as e:
        err = str(e).lower()
        if "unique" in err or "duplicate" in err:
            return jsonify(error="Username or email already exists"), 409
        return jsonify(error="Invalid data"), 400

    return jsonify(user.to_dict()), 201


@users_bp.route("/users/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    try:
        user = User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="User not found"), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    if "username" in data:
        if not isinstance(data["username"], str) or not data["username"].strip():
            return jsonify(error="username must be a non-empty string"), 400
        user.username = data["username"].strip()

    if "email" in data:
        if not isinstance(data["email"], str) or not data["email"].strip():
            return jsonify(error="email must be a non-empty string"), 400
        user.email = data["email"].strip()

    try:
        user.save()
    except IntegrityError:
        return jsonify(error="Username or email already exists"), 409

    return jsonify(user.to_dict())


@users_bp.route("/users/bulk", methods=["POST"])
def bulk_load_users():
    if "file" not in request.files:
        return jsonify(error="No file provided"), 400

    file = request.files["file"]
    stream = io.StringIO(file.stream.read().decode("utf-8"))
    reader = csv.DictReader(stream)

    count = 0
    for row in reader:
        username = row.get("username", "").strip()
        email = row.get("email", "").strip()
        created_at = row.get("created_at", "").strip()

        if not username or not email:
            continue

        try:
            User.create(
                username=username,
                email=email,
                created_at=created_at or datetime.datetime.now(),
            )
            count += 1
        except IntegrityError:
            continue

    return jsonify(count=count), 201
