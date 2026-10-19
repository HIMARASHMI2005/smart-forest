from datetime import datetime
import json
import bcrypt
from backend.app.extensions import db

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    forest_user_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum("USER", "ADMIN", name="user_roles"), nullable=False, default="USER")
    emergency_contact = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="ACTIVE")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    face_profile = db.relationship("FaceProfile", backref="user", uselist=False, cascade="all, delete-orphan")
    locations = db.relationship("Location", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    sos_events = db.relationship("SOSEvent", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    alerts = db.relationship("Alert", backref="user", lazy="dynamic")
    sessions = db.relationship("LoginSession", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    @staticmethod
    def generate_forest_id() -> str:
        import secrets, string
        while True:
            letters = "".join(secrets.choice(string.ascii_uppercase) for _ in range(2))
            digits = "".join(secrets.choice(string.digits) for _ in range(4))
            candidate = f"FOR-{letters}{digits}"
            try:
                if not User.query.filter_by(forest_user_id=candidate).first():
                    return candidate
            except Exception:
                return candidate

    def __init__(self, **kwargs):
        if "forest_user_id" not in kwargs or not kwargs["forest_user_id"]:
            kwargs["forest_user_id"] = self.generate_forest_id()
        super().__init__(**kwargs)

    def set_password(self, password: str):
        salt = bcrypt.gensalt(rounds=12)
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))

    def to_dict(self, include_sensitive=False):
        data = {
            "id": self.id,
            "forest_user_id": self.forest_user_id,
            "unique_id": self.forest_user_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "role": self.role,
            "emergency_contact": self.emergency_contact,
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "has_face_registered": self.face_profile is not None
        }
        if include_sensitive:
            data["password_hash"] = self.password_hash
        return data


class FaceProfile(db.Model):
    __tablename__ = "face_profiles"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    embedding_vector = db.Column(db.JSON, nullable=False)  # 128-dimensional float list
    image_path = db.Column(db.String(255), nullable=True)
    samples_count = db.Column(db.Integer, nullable=False, default=1)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_embedding(self):
        if isinstance(self.embedding_vector, str):
            return json.loads(self.embedding_vector)
        return self.embedding_vector

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "samples_count": self.samples_count,
            "image_path": self.image_path,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None
        }


class LoginSession(db.Model):
    __tablename__ = "login_sessions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    token_id = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
