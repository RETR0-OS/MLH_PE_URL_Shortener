import datetime
import json

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
        query = query.where(Event.url_id == url_id)

    user_id = request.args.get("user_id", type=int)
    if user_id is not None:
        query = query.where(Event.user_id == user_id)

    event_type = request.args.get("event_type")
    if event_type is not None:
        query = query.where(Event.event_type == event_type)

    return jsonify([e.to_dict() for e in query])


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
        url_id=url_id,
        user_id=user_id,
        event_type=event_type.strip(),
        timestamp=datetime.datetime.now(),
        details=json.dumps(details) if isinstance(details, dict) else str(details),
    )

    return jsonify(event.to_dict()), 201
