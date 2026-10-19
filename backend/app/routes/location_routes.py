from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from backend.app.extensions import db
from backend.app.models import User, Location, Alert
from backend.app.services import GeofenceService, NotificationService
from backend.app.utils import api_response

location_bp = Blueprint("location", __name__, url_prefix="/api/location")


def handle_location_update(user_id: int, data: dict):
    """
    Core handler for receiving real device GPS coordinates:
    1. Authenticates user from JWT identity.
    2. Validates latitude (-90 to 90) and longitude (-180 to 180).
    3. Evaluates Shapely Point-in-Polygon against forest zones: Point(lon, lat).
    4. Appends to locations history table without overwriting past coordinates.
    5. Dispatches restricted-zone warnings if entering HIGH/CRITICAL zones.
    6. Broadcasts 'location_update' event via Socket.IO to officer dashboard.
    """
    user = db.session.get(User, user_id)
    if not user:
        return api_response(False, "User not found.", status_code=404)

    raw_lat = data.get("latitude")
    raw_lon = data.get("longitude")

    if raw_lat is None or raw_lon is None:
        return api_response(False, "latitude and longitude are required.", status_code=400)

    try:
        lat = float(raw_lat)
        lon = float(raw_lon)
    except (ValueError, TypeError):
        return api_response(False, "Latitude and longitude must be valid numbers.", status_code=400)

    if not (-90.0 <= lat <= 90.0):
        return api_response(False, f"Latitude out of bounds: {lat}. Must be between -90 and 90.", status_code=400)
    if not (-180.0 <= lon <= 180.0):
        return api_response(False, f"Longitude out of bounds: {lon}. Must be between -180 and 180.", status_code=400)

    accuracy = float(data.get("accuracy", 0.0) or 0.0)
    altitude = float(data.get("altitude")) if data.get("altitude") is not None else None
    heading = float(data.get("heading")) if data.get("heading") is not None else None
    speed = float(data.get("speed")) if data.get("speed") is not None else None

    # Determine forest zone via Shapely Point-in-Polygon (Point(longitude, latitude))
    zone_info = GeofenceService.check_location_risk(lat, lon)
    zone_id = zone_info.get("zone_id")
    zone_name = zone_info.get("zone_name", "General Forest Buffer")
    zone_code = zone_info.get("zone_code", "GENERAL-BUFFER")
    risk_level = zone_info.get("risk_level", "LOW")
    is_restricted = zone_info.get("is_restricted", False)

    # Save to locations history table (never overwrite previous history)
    location = Location(
        user_id=user_id,
        latitude=lat,
        longitude=lon,
        zone_id=zone_id,
        accuracy=accuracy,
        altitude=altitude,
        heading=heading,
        speed=speed,
        timestamp=datetime.utcnow()
    )
    db.session.add(location)
    db.session.commit()

    now_str = location.timestamp.strftime("%Y-%m-%d %H:%M:%S")

    # Restricted zone entry alert
    if is_restricted:
        try:
            alert = Alert(
                alert_type="GEOFENCE_WARNING",
                severity="HIGH" if risk_level == "CRITICAL" else "MEDIUM",
                user_id=user_id,
                zone_id=zone_id,
                latitude=lat,
                longitude=lon,
                message=f"User {user.name} entered restricted zone: {zone_name} ({risk_level})"
            )
            db.session.add(alert)
            db.session.commit()
            NotificationService.broadcast_alert(alert.to_dict())
        except Exception as alert_err:
            print(f"[Alert broadcast warning]: {alert_err}")

    # Real-time WebSocket broadcast to officer/admin dashboard
    telemetry_payload = {
        "user_id": user_id,
        "name": user.name,
        "email": user.email,
        "latitude": lat,
        "longitude": lon,
        "accuracy": accuracy,
        "altitude": altitude,
        "heading": heading,
        "speed": speed,
        "zone_id": zone_id,
        "zone_name": zone_name,
        "zone_code": zone_code,
        "risk_level": risk_level,
        "is_restricted": is_restricted,
        "timestamp": now_str
    }
    NotificationService.broadcast_location_update(telemetry_payload)

    return api_response(True, "Location updated.", {
        "user_id": user_id,
        "name": user.name,
        "email": user.email,
        "latitude": lat,
        "longitude": lon,
        "accuracy": accuracy,
        "altitude": altitude,
        "heading": heading,
        "speed": speed,
        "zone_id": zone_id,
        "zone_name": zone_name,
        "zone_code": zone_code,
        "risk_level": risk_level,
        "is_restricted": is_restricted,
        "timestamp": now_str,
        "zone": zone_info
    })


@location_bp.route("/update", methods=["POST"])
@jwt_required()
def update_user_location():
    """Receives authenticated real device GPS coordinates, stores history, evaluates zone, and broadcasts."""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json(force=True, silent=True) or {}
        return handle_location_update(user_id, data)
    except Exception as e:
        db.session.rollback()
        return api_response(False, f"Location update error: {str(e)}", status_code=500)


@location_bp.route("/current", methods=["GET"])
@jwt_required()
def get_current_location():
    """Returns the authenticated user's latest GPS position and active zone."""
    try:
        user_id = int(get_jwt_identity())
        loc = Location.query.filter_by(user_id=user_id).order_by(Location.id.desc()).first()
        if not loc:
            return api_response(True, "No location history recorded yet.", {"location": None})
        return api_response(True, "Current location.", {"location": loc.to_dict()})
    except Exception as e:
        return api_response(False, f"Location fetch error: {str(e)}", status_code=500)
