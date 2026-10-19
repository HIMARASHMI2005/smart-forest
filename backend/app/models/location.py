from datetime import datetime
from backend.app.extensions import db

class Location(db.Model):
    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    latitude = db.Column(db.Numeric(10, 8), nullable=False)
    longitude = db.Column(db.Numeric(11, 8), nullable=False)
    zone_id = db.Column(db.Integer, db.ForeignKey("forest_zones.id", ondelete="SET NULL"), nullable=True)
    accuracy = db.Column(db.Float, nullable=False, default=0.0)
    altitude = db.Column(db.Float, nullable=True)
    heading = db.Column(db.Float, nullable=True)
    speed = db.Column(db.Float, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    def to_dict(self):
        zone_name = self.zone.name if self.zone else "General Forest Buffer"
        zone_code = self.zone.code if self.zone else "GENERAL-BUFFER"
        risk_level = self.zone.risk_level if self.zone else "LOW"
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.user.name if self.user else "Registered User",
            "user_name": self.user.name if self.user else "Registered User",
            "user_email": self.user.email if self.user else "",
            "latitude": float(self.latitude),
            "longitude": float(self.longitude),
            "accuracy": float(self.accuracy or 0.0),
            "altitude": float(self.altitude) if self.altitude is not None else None,
            "heading": float(self.heading) if self.heading is not None else None,
            "speed": float(self.speed) if self.speed is not None else None,
            "zone_id": self.zone_id,
            "zone_name": zone_name,
            "zone_code": zone_code,
            "risk_level": risk_level,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else None
        }
