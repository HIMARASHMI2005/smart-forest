from datetime import datetime
import json
from backend.app.extensions import db

class Detection(db.Model):
    __tablename__ = "detections"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    person_count = db.Column(db.Integer, nullable=False, default=0)
    identified_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_unknown = db.Column(db.Boolean, nullable=False, default=False)
    confidence = db.Column(db.Float, nullable=False, default=0.0)
    bounding_boxes = db.Column(db.JSON, nullable=True)
    image_snapshot = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    identified_user = db.relationship("User", backref="detections")

    def to_dict(self):
        return {
            "id": self.id,
            "person_count": self.person_count,
            "identified_user_id": self.identified_user_id,
            "identified_user_name": self.identified_user.name if self.identified_user else ("Unknown Person" if self.is_unknown else "None"),
            "is_unknown": self.is_unknown,
            "confidence": round(self.confidence, 4),
            "bounding_boxes": self.bounding_boxes if isinstance(self.bounding_boxes, list) else (json.loads(self.bounding_boxes) if self.bounding_boxes else []),
            "image_snapshot": self.image_snapshot,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else None
        }
