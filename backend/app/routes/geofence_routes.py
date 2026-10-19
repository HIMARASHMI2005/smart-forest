from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from backend.app.extensions import db
from backend.app.models import ForestZone
from backend.app.services import GeofenceService
from backend.app.utils import api_response

geofence_bp = Blueprint("geofence", __name__, url_prefix="/api/geofence")


@geofence_bp.route("/zones", methods=["GET"])
def get_zones():
    zones = GeofenceService.get_all_active_zones_geojson()
    return api_response(True, "Forest zones.", {"zones": zones})


@geofence_bp.route("/check", methods=["POST"])
@jwt_required(optional=True)
def check_location():
    data = request.get_json(force=True, silent=True) or {}
    lat = data.get("latitude")
    lon = data.get("longitude")
    if lat is None or lon is None:
        return api_response(False, "latitude and longitude required.", status_code=400)
    try:
        result = GeofenceService.check_location_risk(float(lat), float(lon))
        return api_response(True, "Zone check complete.", result)
    except Exception as e:
        return api_response(False, f"Geo-fence check error: {str(e)}", status_code=500)
