from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from backend.app.extensions import db
from backend.app.models import User, Location, Detection, Alert
from backend.app.utils import api_response
from backend.app.services import GeofenceService

user_bp = Blueprint("user", __name__, url_prefix="/api/user")


@user_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    user = User.query.get(int(get_jwt_identity()))
    if not user:
        return api_response(False, "User not found.", status_code=404)
    return api_response(True, "User profile.", {"user": user.to_dict()})


@user_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    try:
        user = User.query.get(int(get_jwt_identity()))
        if not user:
            return api_response(False, "User not found.", status_code=404)
        data = request.get_json(force=True, silent=True) or {}
        if "name" in data:
            user.name = str(data["name"]).strip()
        if "phone" in data:
            user.phone = str(data["phone"]).strip()
        if "emergency_contact" in data:
            user.emergency_contact = str(data["emergency_contact"]).strip()
        db.session.commit()
        return api_response(True, "Profile updated.", {"user": user.to_dict()})
    except Exception as e:
        db.session.rollback()
        return api_response(False, f"Update error: {str(e)}", status_code=500)


@user_bp.route("/location", methods=["POST"])
@jwt_required()
def update_location():
    """Receives user GPS coordinates, checks geo-fence, stores location (delegates to handle_location_update)."""
    try:
        from backend.app.routes.location_routes import handle_location_update
        user_id = int(get_jwt_identity())
        data = request.get_json(force=True, silent=True) or {}
        return handle_location_update(user_id, data)
    except Exception as e:
        db.session.rollback()
        return api_response(False, f"Location update error: {str(e)}", status_code=500)


@user_bp.route("/location/current", methods=["GET"])
@jwt_required()
def get_user_current_location():
    """Returns the authenticated user's latest GPS position and active zone."""
    try:
        user_id = int(get_jwt_identity())
        loc = Location.query.filter_by(user_id=user_id).order_by(Location.id.desc()).first()
        if not loc:
            return api_response(True, "No location history recorded yet.", {"location": None})
        return api_response(True, "Current location.", {"location": loc.to_dict()})
    except Exception as e:
        return api_response(False, f"Location fetch error: {str(e)}", status_code=500)


@user_bp.route("/alerts", methods=["GET"])
@jwt_required()
def get_my_alerts():
    user_id = int(get_jwt_identity())
    alerts = Alert.query.filter_by(user_id=user_id).order_by(Alert.created_at.desc()).limit(50).all()
    return api_response(True, "User alerts.", {"alerts": [a.to_dict() for a in alerts]})
