from datetime import datetime
from backend.app.extensions import db

class Alert(db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    alert_type = db.Column(db.String(50), nullable=False)
    severity = db.Column(
        db.Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="alert_severities"),
        nullable=False,
        default="MEDIUM",
        index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    zone_id = db.Column(db.Integer, db.ForeignKey("forest_zones.id", ondelete="SET NULL"), nullable=True)
    latitude = db.Column(db.Numeric(10, 8), nullable=True)
    longitude = db.Column(db.Numeric(11, 8), nullable=True)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.Enum("ACTIVE", "ACKNOWLEDGED", "RESOLVED", name="alert_statuses"),
        nullable=False,
        default="ACTIVE",
        index=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "user_id": self.user_id,
            "user_name": self.user.name if self.user else "Anonymous / Unknown",
            "zone_id": self.zone_id,
            "zone_name": self.zone.name if self.zone else "General Forest Perimeter",
            "latitude": float(self.latitude) if self.latitude is not None else None,
            "longitude": float(self.longitude) if self.longitude is not None else None,
            "message": self.message,
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None
        }
