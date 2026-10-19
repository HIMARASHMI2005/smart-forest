from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from functools import wraps
from backend.app.extensions import db
from backend.app.models import User, Alert, Detection, SOSEvent, Location, ForestZone
from backend.app.utils import api_response

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user = db.session.get(User, int(get_jwt_identity()))
        if not user or user.role not in ["ADMIN", "OFFICER"]:
            return api_response(False, "Admin or Officer access required.", status_code=403)
        return fn(*args, **kwargs)
    return wrapper


@admin_bp.route("/stats", methods=["GET"])
@admin_required
def get_stats():
    total_users   = User.query.count()
    active_users  = User.query.filter_by(status="ACTIVE").count()
    total_alerts  = Alert.query.filter_by(status="ACTIVE").count()
    total_sos     = SOSEvent.query.filter_by(status="OPEN").count()
    total_zones   = ForestZone.query.filter_by(is_active=True).count()
    total_dets    = Detection.query.count()
    unknown_dets  = Detection.query.filter_by(is_unknown=True).count()
    return api_response(True, "System statistics.", {
        "total_users": total_users, "active_users": active_users,
        "active_alerts": total_alerts, "open_sos_events": total_sos,
        "active_zones": total_zones, "total_detections": total_dets,
        "unknown_detections": unknown_dets
    })


@admin_bp.route("/users", methods=["GET"])
@admin_required
def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return api_response(True, "All users.", {"users": [u.to_dict() for u in users]})


@admin_bp.route("/alerts", methods=["GET"])
@admin_required
def list_alerts():
    status = request.args.get("status", None)
    query = Alert.query.order_by(Alert.created_at.desc())
    if status:
        query = query.filter_by(status=status.upper())
    alerts = query.limit(100).all()
    return api_response(True, "Alerts.", {"alerts": [a.to_dict() for a in alerts]})


@admin_bp.route("/alerts/<int:alert_id>/acknowledge", methods=["PUT"])
@admin_required
def acknowledge_alert(alert_id):
    alert = Alert.query.get_or_404(alert_id)
    alert.status = "ACKNOWLEDGED"
    db.session.commit()
    return api_response(True, "Alert acknowledged.", {"alert": alert.to_dict()})


@admin_bp.route("/alerts/<int:alert_id>/resolve", methods=["PUT"])
@admin_required
def resolve_alert(alert_id):
    alert = Alert.query.get_or_404(alert_id)
    alert.status = "RESOLVED"
    db.session.commit()
    return api_response(True, "Alert resolved.", {"alert": alert.to_dict()})


@admin_bp.route("/sos", methods=["GET"])
@admin_required
def list_sos():
    sos_events = SOSEvent.query.order_by(SOSEvent.created_at.desc()).limit(50).all()
    return api_response(True, "SOS events.", {"sos_events": [s.to_dict() for s in sos_events]})


@admin_bp.route("/sos/<int:sos_id>/acknowledge", methods=["PUT"])
@admin_required
def acknowledge_sos(sos_id):
    sos = SOSEvent.query.get_or_404(sos_id)
    sos.status = "ACKNOWLEDGED"
    db.session.commit()
    from backend.app.services import NotificationService
    NotificationService.broadcast_sos({"event": "acknowledged", "sos_id": sos_id})
    return api_response(True, "SOS acknowledged.", {"sos": sos.to_dict()})


@admin_bp.route("/sos/<int:sos_id>/resolve", methods=["PUT"])
@admin_required
def resolve_sos(sos_id):
    from datetime import datetime
    sos = SOSEvent.query.get_or_404(sos_id)
    sos.status = "RESOLVED"
    sos.resolved_at = datetime.utcnow()
    db.session.commit()
    return api_response(True, "SOS resolved.", {"sos": sos.to_dict()})


@admin_bp.route("/detections", methods=["GET"])
@admin_required
def list_detections():
    detections = Detection.query.order_by(Detection.timestamp.desc()).limit(100).all()
    return api_response(True, "Detections.", {"detections": [d.to_dict() for d in detections]})


@admin_bp.route("/zones", methods=["GET"])
@admin_required
def list_zones():
    zones = ForestZone.query.all()
    return api_response(True, "Forest zones.", {"zones": [z.to_dict() for z in zones]})


@admin_bp.route("/locations/current", methods=["GET"])
@admin_required
def get_admin_current_locations():
    """Returns the latest real GPS location for every active registered user."""
    # Subquery: get max location id per user_id
    subquery = db.session.query(
        Location.user_id,
        db.func.max(Location.id).label("max_id")
    ).group_by(Location.user_id).subquery()

    latest_locs = db.session.query(Location).join(
        subquery, Location.id == subquery.c.max_id
    ).join(User, Location.user_id == User.id).filter(User.status == "ACTIVE").all()

    locations = []
    for loc in latest_locs:
        d = loc.to_dict()
        user_name = loc.user.name if loc.user else "Registered User"
        d["name"] = user_name
        d["user_name"] = user_name
        locations.append(d)
    return api_response(True, "Current locations of active registered users.", {"locations": locations})

