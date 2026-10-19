from datetime import datetime
import json
from backend.app.extensions import db

class ForestZone(db.Model):
    __tablename__ = "forest_zones"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    boundary_geojson = db.Column(db.JSON, nullable=False)  # GeoJSON Polygon coordinates
    risk_level = db.Column(
        db.Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="risk_levels"),
        nullable=False,
        default="LOW"
    )
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Relationships
    locations = db.relationship("Location", backref="zone", lazy="dynamic")
    alerts = db.relationship("Alert", backref="zone", lazy="dynamic")
    sos_events = db.relationship("SOSEvent", backref="zone", lazy="dynamic")

    def get_geojson(self):
        if isinstance(self.boundary_geojson, str):
            return json.loads(self.boundary_geojson)
        return self.boundary_geojson

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "risk_level": self.risk_level,
            "description": self.description,
            "is_active": self.is_active,
            "boundary_geojson": self.get_geojson()
        }
