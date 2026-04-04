from flask import Blueprint, jsonify

from app.models.event import Event

events_bp = Blueprint("events", __name__)


@events_bp.route("/events", methods=["GET"])
def list_events():
    query = Event.select().order_by(Event.id)
    return jsonify([e.to_dict() for e in query])
