from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from backend.app.extensions import db
from backend.app.models import User, SOSEvent, Alert
from backend.app.services import GeofenceService, NotificationService
from backend.app.utils import api_response

sos_bp = Blueprint("sos", __name__, url_prefix="/api/sos")

VALID_EMERGENCY_TYPES = ["INJURY", "WILD_ANIMAL", "LOST", "FIRE", "OTHER"]


@sos_bp.route("/trigger", methods=["POST"])
@jwt_required()
def trigger_sos():
    try:
        user_id = int(get_jwt_identity())
        user = db.session.get(User, user_id)
        if not user:
            return api_response(False, "User not found.", status_code=404)

        data = request.get_json(force=True, silent=True) or {}
        lat           = data.get("latitude")
        lon           = data.get("longitude")
        emergency_type = str(data.get("emergency_type", "OTHER")).upper()
        message        = str(data.get("message", "")).strip()

        if lat is None or lon is None:
            return api_response(False, "GPS coordinates are required for SOS.", status_code=400)
        if emergency_type not in VALID_EMERGENCY_TYPES:
            emergency_type = "OTHER"

        zone_info = GeofenceService.check_location_risk(float(lat), float(lon))

        sos = SOSEvent(
            user_id=user_id,
            latitude=float(lat),
            longitude=float(lon),
            zone_id=zone_info.get("zone_id"),
            emergency_type=emergency_type,
            message=message or f"Emergency SOS by {user.name}",
            status="OPEN"
        )
        db.session.add(sos)

        # Create CRITICAL alert
        alert = Alert(
            alert_type="SOS_EMERGENCY",
            severity="CRITICAL",
            user_id=user_id,
            zone_id=zone_info.get("zone_id"),
            latitude=float(lat),
            longitude=float(lon),
            message=f"[SOS ALERT] - {user.name} | {emergency_type} | {message or 'Emergency!'}"
        )
        db.session.add(alert)
        db.session.commit()

        # Real-time broadcast to admin dashboard
        sos_payload = {**sos.to_dict(), "alert_id": alert.id}
        NotificationService.broadcast_sos(sos_payload)
        NotificationService.broadcast_alert(alert.to_dict())

        return api_response(True, "SOS sent! Help is on the way.", {
            "sos_id": sos.id,
            "zone": zone_info,
            "status": "OPEN"
        }, status_code=201)

    except Exception as e:
        db.session.rollback()
        return api_response(False, f"SOS error: {str(e)}", status_code=500)


@sos_bp.route("/my-events", methods=["GET"])
@jwt_required()
def my_sos_events():
    user_id = int(get_jwt_identity())
    events = SOSEvent.query.filter_by(user_id=user_id).order_by(SOSEvent.created_at.desc()).all()
    return api_response(True, "Your SOS history.", {"sos_events": [s.to_dict() for s in events]})
