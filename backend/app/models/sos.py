from datetime import datetime
from backend.app.extensions import db

class SOSEvent(db.Model):
    __tablename__ = "sos_events"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    latitude = db.Column(db.Numeric(10, 8), nullable=False)
    longitude = db.Column(db.Numeric(11, 8), nullable=False)
    zone_id = db.Column(db.Integer, db.ForeignKey("forest_zones.id", ondelete="SET NULL"), nullable=True)
    emergency_type = db.Column(db.String(50), nullable=False)  # INJURY, WILD_ANIMAL, LOST, FIRE, OTHER
    message = db.Column(db.Text, nullable=True)
    video_filename = db.Column(db.String(255), nullable=True)
    status = db.Column(
        db.Enum("OPEN", "ACKNOWLEDGED", "RESOLVED", name="sos_statuses"),
        nullable=False,
        default="OPEN",
        index=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        forest_uid = self.user.forest_user_id if (self.user and hasattr(self.user, "forest_user_id")) else ""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "forest_user_id": forest_uid,
            "unique_id": forest_uid,
            "user_name": self.user.name if self.user else "Unknown Personnel",
            "name": self.user.name if self.user else "Unknown Personnel",
            "user_phone": self.user.phone if self.user else "N/A",
            "emergency_contact": self.user.emergency_contact if self.user else "N/A",
            "latitude": float(self.latitude),
            "longitude": float(self.longitude),
            "zone_id": self.zone_id,
            "zone_name": self.zone.name if self.zone else "Outside Defined Zones",
            "emergency_type": self.emergency_type,
            "message": self.message,
            "video_filename": self.video_filename,
            "status": self.status,
            "timestamp": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "resolved_at": self.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if self.resolved_at else None
        }
