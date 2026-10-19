import os
import cv2
import base64
import numpy as np
from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity, get_jwt
)
from datetime import datetime
from backend.app.extensions import db
from backend.app.models import User, FaceProfile, LoginSession
from backend.app.utils import api_response
from backend.app.config import Config

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Unified registration endpoint:
    1. Creates User with bcrypt password hash and auto-generated forest_user_id (FOR-XXXXXX).
    2. If face_images (base64 array, 1-5 real webcam photos) are provided:
       - Saves JPEG crops to dataset/faces/<forest_user_id>/face_01.jpg..face_05.jpg
       - Computes 128-D embedding per sample via ForestFaceNet
       - Computes L2-normalized centroid prototype
       - Creates FaceProfile with centroid embedding
       - Also writes centroid to legacy visitor_face_embeddings for recognition cache
    3. Returns JWT access_token + user dict.
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        name      = str(data.get("name", "")).strip()
        email     = str(data.get("email", "")).strip().lower()
        phone     = str(data.get("phone", "")).strip()
        password  = str(data.get("password", ""))

        # Accept emergency_contact as single field or name+phone pair
        emergency = str(data.get("emergency_contact", "")).strip()
        if not emergency:
            ec_name = str(data.get("emergency_contact_name", "")).strip()
            ec_phone = str(data.get("emergency_contact_phone", "")).strip()
            if ec_name and ec_phone:
                emergency = f"{ec_name} ({ec_phone})"
            elif ec_phone:
                emergency = ec_phone

        # Face images (base64 array from webcam capture)
        face_images = data.get("face_images") or []

        if not all([name, email, phone, password]):
            return api_response(False, "Name, email, phone and password are required.", status_code=400)
        if len(password) < 6:
            return api_response(False, "Password must be at least 6 characters.", status_code=400)
        if User.query.filter_by(email=email).first():
            return api_response(False, "An account with this email already exists.", status_code=409)

        # Create user with auto-generated forest_user_id
        user = User(name=name, email=email, phone=phone, emergency_contact=emergency)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        forest_id = user.forest_user_id
        face_registered = False
        samples_count = 0
        face_thumbnail = ""

        # Process face enrollment if images provided
        if face_images:
            face_result = _enroll_face_biometrics(face_images, user)
            if face_result["success"]:
                face_registered = True
                samples_count = face_result["samples_count"]
                face_thumbnail = face_result.get("thumbnail", "")
            else:
                db.session.rollback()
                return api_response(False, face_result.get("error", "Photo capture failed: Real photographs required."), status_code=400)

        # Issue JWT token immediately after registration
        token = create_access_token(identity=str(user.id))

        # Create login session
        session = LoginSession(
            user_id=user.id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent", ""),
            token_id=token[:50]
        )
        db.session.add(session)
        db.session.commit()

        return api_response(True, "Registration successful!", {
            "user": user.to_dict(),
            "access_token": token,
            "forest_user_id": forest_id,
            "unique_id": forest_id,
            "face_registered": face_registered,
            "samples_count": samples_count,
            "face_thumbnail": face_thumbnail,
            "registered_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else None
        }, status_code=201)

    except Exception as e:
        db.session.rollback()
        return api_response(False, f"Registration failed: {str(e)}", status_code=500)


from ai.face_identification.face_validator import validate_real_photograph
from ai.face_identification.preprocessing import custom_localize_face

def _enroll_face_biometrics(images_b64: list, user) -> dict:
    """
    Processes real webcam photos for face biometric enrollment:
    1. Validates authenticity (rejects cartoon, smiley, monochrome, or synthetic images).
    2. Localizes face via custom_localize_face() (strictly zero pretrained weights/XML).
    3. Standardizes to 112x112 normalized crop.
    4. Computes 128-D embedding via ForestFaceNet for each sample.
    5. Computes L2-normalized centroid prototype.
    6. Saves authentic crops to dataset/faces/<forest_user_id>/face_01.jpg..face_05.jpg.
    7. Updates canonical FaceProfile (SQLAlchemy) and legacy tables for cache compatibility.
    8. Invalidate and reloads active recognition index.
    """
    try:
        from backend.app.ai import get_face_identifier
        identifier = get_face_identifier()
    except Exception as e:
        return {"success": False, "error": f"Face model load error: {e}"}

    project_root = Config.PROJECT_ROOT
    enrollment_dir = os.path.join(project_root, "dataset", "faces", user.forest_user_id)

    valid_embeddings = []
    saved_samples = []
    first_thumb_b64 = ""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for idx, b64_str in enumerate(images_b64[:10]):
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        try:
            img_bytes = base64.b64decode(b64_str)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                continue
        except Exception:
            continue

        # Strict real photograph validation
        is_real, reason = validate_real_photograph(img, is_pre_cropped=False)
        if not is_real:
            is_real, reason = validate_real_photograph(img, min_width=100, min_height=100, is_pre_cropped=True)
            if not is_real:
                if os.path.exists(enrollment_dir) and not os.listdir(enrollment_dir):
                    try:
                        os.rmdir(enrollment_dir)
                    except Exception:
                        pass
                return {"success": False, "error": f"Photo capture failed for sample #{idx+1}: {reason}"}

        # Pure custom face localization (strictly zero pretrained models / zero XML)
        face_crop, bbox = custom_localize_face(img)
        if face_crop is None or face_crop.size == 0:
            face_crop = cv2.resize(img, (112, 112), interpolation=cv2.INTER_AREA)

        emb = identifier.get_embedding(face_crop)
        if emb is None:
            continue
        norm = np.linalg.norm(emb)
        if norm <= 0:
            continue
        normalized_emb = (emb / norm).astype(np.float32)
        valid_embeddings.append(normalized_emb)

        # Save real photograph crop to dataset/faces/<forest_user_id>/face_XX.jpg
        os.makedirs(enrollment_dir, exist_ok=True)
        sample_filename = f"face_{idx+1:02d}.jpg"
        sample_path = os.path.join(enrollment_dir, sample_filename)
        cv2.imwrite(sample_path, face_crop)
        saved_samples.append((idx + 1, f"dataset/faces/{user.forest_user_id}/{sample_filename}", normalized_emb.tobytes()))

        if not first_thumb_b64:
            thumb = cv2.resize(face_crop, (100, 100))
            _, enc = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 85])
            first_thumb_b64 = f"data:image/jpeg;base64,{base64.b64encode(enc).decode('utf-8')}"

    if not valid_embeddings:
        if os.path.exists(enrollment_dir) and not os.listdir(enrollment_dir):
            try:
                os.rmdir(enrollment_dir)
            except Exception:
                pass
        return {"success": False, "error": "No valid faces could be extracted from photographs."}

    # Compute L2-normalized centroid prototype
    centroid = np.mean(valid_embeddings, axis=0)
    c_norm = np.linalg.norm(centroid)
    if c_norm > 0:
        centroid = centroid / c_norm
    centroid_list = centroid.astype(np.float32).tolist()

    # Create canonical FaceProfile in SQLAlchemy
    existing_fp = FaceProfile.query.filter_by(user_id=user.id).first()
    if existing_fp:
        existing_fp.embedding_vector = centroid_list
        existing_fp.image_path = f"dataset/faces/{user.forest_user_id}/face_01.jpg"
        existing_fp.samples_count = len(valid_embeddings)
        existing_fp.updated_at = datetime.utcnow()
    else:
        fp = FaceProfile(
            user_id=user.id,
            embedding_vector=centroid_list,
            image_path=f"dataset/faces/{user.forest_user_id}/face_01.jpg",
            samples_count=len(valid_embeddings)
        )
        db.session.add(fp)
    db.session.commit()

    # Also write to legacy visitor_face_embeddings for recognition cache compatibility
    _sync_to_legacy_cache(user, centroid, saved_samples, first_thumb_b64, now_str)

    # Reload recognition cache
    try:
        from backend.app.services.visitor_service import reload_embeddings_cache
        reload_embeddings_cache()
    except Exception:
        pass

    return {
        "success": True,
        "samples_count": len(valid_embeddings),
        "thumbnail": first_thumb_b64
    }


def _extract_face_crop(img_bgr, fx, fy, fw, fh, pad_ratio=0.0):
    """Extracts a standardized face crop (same logic as visitor_service)."""
    ih, iw = img_bgr.shape[:2]
    pw = int(fw * pad_ratio)
    ph = int(fh * pad_ratio)
    x1 = max(0, fx - pw)
    y1 = max(0, fy - ph)
    x2 = min(iw, fx + fw + pw)
    y2 = min(ih, fy + fh + ph)
    return img_bgr[y1:y2, x1:x2]


def _sync_to_legacy_cache(user, centroid_np, saved_samples, thumbnail_b64, now_str):
    """
    Writes face enrollment data to legacy sqlite3 tables (visitor_face_embeddings,
    visitor_face_samples, registrations) so the existing recognition cache reload
    and officer dashboard remain functional during the migration period.
    """
    import sqlite3
    project_root = Config.PROJECT_ROOT
    db_path = os.path.join(project_root, "smart_forest.db")

    centroid_bytes = centroid_np.astype(np.float32).tobytes()

    try:
        conn = sqlite3.connect(db_path)
        # Ensure legacy tables exist
        conn.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unique_id TEXT UNIQUE, name TEXT, phone TEXT, email TEXT,
                registered_at TEXT, latitude REAL DEFAULT 0, longitude REAL DEFAULT 0,
                gps_status TEXT DEFAULT 'Pending', last_active TEXT,
                status TEXT DEFAULT 'Active', face_registered INTEGER DEFAULT 0,
                samples_count INTEGER DEFAULT 0, current_zone TEXT DEFAULT 'Pending',
                risk_level TEXT DEFAULT 'LOW'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS visitor_face_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unique_id TEXT UNIQUE, name TEXT, embedding BLOB,
                face_thumbnail TEXT, samples_count INTEGER DEFAULT 1, created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS visitor_face_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unique_id TEXT, sample_index INTEGER, image_path TEXT,
                embedding BLOB, created_at TEXT
            )
        """)

        uid = user.forest_user_id

        # Upsert into registrations
        existing = conn.execute("SELECT 1 FROM registrations WHERE unique_id = ?", (uid,)).fetchone()
        if not existing:
            conn.execute("""
                INSERT INTO registrations (unique_id, name, phone, email, registered_at, last_active, status, face_registered, samples_count)
                VALUES (?, ?, ?, ?, ?, ?, 'Active', 1, ?)
            """, (uid, user.name, user.phone, user.email, now_str, now_str, len(saved_samples)))
        else:
            conn.execute("""
                UPDATE registrations SET face_registered = 1, samples_count = ?, name = ?, last_active = ?
                WHERE unique_id = ?
            """, (len(saved_samples), user.name, now_str, uid))

        # Upsert centroid into visitor_face_embeddings
        conn.execute("DELETE FROM visitor_face_embeddings WHERE unique_id = ?", (uid,))
        conn.execute("""
            INSERT INTO visitor_face_embeddings (unique_id, name, embedding, face_thumbnail, samples_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (uid, user.name, sqlite3.Binary(centroid_bytes), thumbnail_b64, len(saved_samples), now_str))

        # Insert individual samples
        conn.execute("DELETE FROM visitor_face_samples WHERE unique_id = ?", (uid,))
        for s_idx, s_path, s_emb_bytes in saved_samples:
            conn.execute("""
                INSERT INTO visitor_face_samples (unique_id, sample_index, image_path, embedding, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (uid, s_idx, s_path, sqlite3.Binary(s_emb_bytes), now_str))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[_sync_to_legacy_cache error]: {e}")


@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data     = request.get_json(force=True, silent=True) or {}
        email    = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))

        if not email or not password:
            return api_response(False, "Email and password are required.", status_code=400)

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            return api_response(False, "Invalid email or password.", status_code=401)
        if user.status != "ACTIVE":
            return api_response(False, "Account is disabled. Contact administrator.", status_code=403)

        token = create_access_token(identity=str(user.id))

        session = LoginSession(
            user_id=user.id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent", ""),
            token_id=token[:50]
        )
        db.session.add(session)
        db.session.commit()

        return api_response(True, "Login successful.", {
            "access_token": token,
            "user": user.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return api_response(False, f"Login error: {str(e)}", status_code=500)


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def current_user():
    user = db.session.get(User, int(get_jwt_identity()))
    if not user:
        return api_response(False, "User not found.", status_code=404)
    return api_response(True, "Current user info.", {"user": user.to_dict()})


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    # JWT stateless - client should discard token.
    return api_response(True, "Logged out successfully.")
