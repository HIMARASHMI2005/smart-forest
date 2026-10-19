from backend.app.routes.auth_routes import auth_bp
from backend.app.routes.user_routes import user_bp
from backend.app.routes.admin_routes import admin_bp
from backend.app.routes.ai_routes import ai_bp
from backend.app.routes.geofence_routes import geofence_bp
from backend.app.routes.sos_routes import sos_bp
from backend.app.routes.views import views_bp
from backend.app.routes.visitor_routes import visitor_bp
from backend.app.routes.location_routes import location_bp

__all__ = ["auth_bp", "user_bp", "admin_bp", "ai_bp", "geofence_bp", "sos_bp", "views_bp", "visitor_bp", "location_bp"]

