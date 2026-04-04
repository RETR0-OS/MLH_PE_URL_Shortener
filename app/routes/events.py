import datetime

from flask import Blueprint, jsonify, request

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


@events_bp.route("/events/<int:event_id>", methods=["GET"])
def get_event(event_id):
    try:
        event = Event.get_by_id(event_id)
    except Event.DoesNotExist:
        return jsonify(error="Event not found"), 404
    return jsonify(event.to_dict())


@events_bp.route("/events/<int:event_id>", methods=["PUT"])
def update_event(event_id):
    try:
        event = Event.get_by_id(event_id)
    except Event.DoesNotExist:
        return jsonify(error="Event not found"), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    if "event_type" in data:
        if not isinstance(data["event_type"], str) or not data["event_type"].strip():
            return jsonify(error="event_type must be a non-empty string"), 400
        event.event_type = data["event_type"].strip()
    if "details" in data:
        event.details = data["details"]
    if "url_id" in data:
        if not isinstance(data["url_id"], int):
            return jsonify(error="url_id must be an integer"), 400
        try:
            Url.get_by_id(data["url_id"])
        except Url.DoesNotExist:
            return jsonify(error="URL not found"), 404
        event.url_id = data["url_id"]
    if "user_id" in data:
        if not isinstance(data["user_id"], int):
            return jsonify(error="user_id must be an integer"), 400
        try:
            User.get_by_id(data["user_id"])
        except User.DoesNotExist:
            return jsonify(error="User not found"), 404
        event.user_id = data["user_id"]

    event.timestamp = datetime.datetime.now()
    event.save()

    return jsonify(event.to_dict())


@events_bp.route("/events", methods=["POST"])
def create_event():
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    url_id = data.get("url_id")
    user_id = data.get("user_id")
    event_type = data.get("event_type")
    details = data.get("details", {})

    if url_id is None or not isinstance(url_id, int):
        return jsonify(error="url_id must be an integer"), 400
    if user_id is None or not isinstance(user_id, int):
        return jsonify(error="user_id must be an integer"), 400
    if not isinstance(event_type, str) or not event_type.strip():
        return jsonify(error="event_type must be a non-empty string"), 400

    try:
        Url.get_by_id(url_id)
    except Url.DoesNotExist:
        return jsonify(error="URL not found"), 404

    try:
        User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="User not found"), 404

    event = Event.create(
        url=url_id,
        user=user_id,
        event_type=event_type.strip(),
        timestamp=datetime.datetime.now(),
        details=details,
    )

    return jsonify(event.to_dict()), 201
