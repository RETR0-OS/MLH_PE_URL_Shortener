from flask import Blueprint, jsonify, request

from app.database import db
from app.models.event import Event
from app.models.url import Url
from app.models.user import User

events_bp = Blueprint("events", __name__)


@events_bp.route("/events", methods=["GET"])
def list_events():
    query = Event.select().order_by(Event.id)

    url_id = request.args.get("url_id", type=int)
    if url_id is not None:
        query = query.where(Event.url == url_id)

    user_id = request.args.get("user_id", type=int)
    if user_id is not None:
        query = query.where(Event.user == user_id)

    event_type = request.args.get("event_type")
    if event_type is not None:
        query = query.where(Event.event_type == event_type)

    return jsonify([e.to_dict() for e in query])


@events_bp.route("/events", methods=["POST"])
def create_event():
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Request body is required"), 400

    required = ["url_id", "user_id", "event_type"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify(error=f"Missing fields: {', '.join(missing)}"), 400

    try:
        Url.get_by_id(data["url_id"])
    except Url.DoesNotExist:
        return jsonify(error=f"URL {data['url_id']} not found"), 400

    try:
        User.get_by_id(data["user_id"])
    except User.DoesNotExist:
        return jsonify(error=f"User {data['user_id']} not found"), 400

    with db.atomic():
        event = Event.create(
            url=data["url_id"],
            user=data["user_id"],
            event_type=data["event_type"],
            details=data.get("details", {}),
        )

    return jsonify(event.to_dict()), 201


@events_bp.route("/events/<int:event_id>", methods=["GET"])
def get_event(event_id):
    try:
        event = Event.get_by_id(event_id)
    except Event.DoesNotExist:
        return jsonify(error="Event not found"), 404

    return jsonify(event.to_dict())


@events_bp.route("/events/<int:event_id>", methods=["DELETE"])
def delete_event(event_id):
    try:
        event = Event.get_by_id(event_id)
    except Event.DoesNotExist:
        return jsonify(error="Event not found"), 404

    event.delete_instance()
    return "", 204
