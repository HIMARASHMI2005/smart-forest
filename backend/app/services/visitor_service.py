import os
import cv2
import time
import shutil
import base64
import sqlite3
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from ai.face_identification.face_validator import validate_real_photograph
from ai.face_identification.preprocessing import custom_localize_face

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATABASE_PATH = os.path.join(project_root, "smart_forest.db")
SOS_FOLDER = os.path.join(project_root, "frontend", "static", "uploads", "sos")

# Global in-memory cache for fast face matching
REGISTERED_EMBEDDINGS_CACHE = []
LAST_INTRUSION_TIMES = {}  # track_id -> timestamp
ALERT_COOLDOWN_SECONDS = 10.0

# Geo-fence tracking state and alert cooldown
VISITOR_ZONE_STATE = {}  # unique_id -> {"last_zone_code": ..., "last_risk_level": ..., "last_alert_time": ...}
GEOFENCE_ALERT_COOLDOWN_SECONDS = 15.0

# Calibrated Recognition Thresholds for ForestFaceNet
# Same person: >= 0.85; Different person: <= 0.35
MATCH_THRESHOLD = 0.60
MARGIN_THRESHOLD = 0.08  # Minimum margin between best and 2nd best candidate to reject ambiguity


def db_conn(row_factory=False):
    db = sqlite3.connect(DATABASE_PATH)
    if row_factory:
        db.row_factory = sqlite3.Row
    return db


def init_visitor_tables():
    """Ensures SQLite tables for visitor passes, face biometrics, samples, locations, and SOS alerts exist."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    os.makedirs(SOS_FOLDER, exist_ok=True)

    with db_conn() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unique_id TEXT UNIQUE,
                name TEXT,
                phone TEXT,
                email TEXT,
                registered_at TEXT,
                latitude REAL DEFAULT 0,
                longitude REAL DEFAULT 0,
                gps_status TEXT DEFAULT 'Pending',
                last_active TEXT,
                status TEXT DEFAULT 'Active',
                face_registered INTEGER DEFAULT 0,
                samples_count INTEGER DEFAULT 0,
                current_zone TEXT DEFAULT 'Pending',
                risk_level TEXT DEFAULT 'LOW'
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS visitor_face_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unique_id TEXT UNIQUE,
                name TEXT,
                embedding BLOB,
                face_thumbnail TEXT,
                samples_count INTEGER DEFAULT 1,
                created_at TEXT
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS visitor_face_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unique_id TEXT,
                sample_index INTEGER,
                image_path TEXT,
                embedding BLOB,
                created_at TEXT
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS recognition_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_id INTEGER,
                unique_id TEXT,
                name TEXT,
                status TEXT,
                zone TEXT,
                confidence REAL,
                details TEXT,
                timestamp TEXT
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS sos_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unique_id TEXT,
                name TEXT,
                timestamp TEXT,
                latitude REAL,
                longitude REAL,
                video_filename TEXT,
                status TEXT DEFAULT 'TRIGGERED'
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                event_type TEXT,
                people INTEGER,
                zone TEXT,
                confidence REAL,
                details TEXT
            )
        """)

        # Migration helpers for registrations table
        cursor = db.execute("PRAGMA table_info(registrations)")
        reg_cols = [row[1] for row in cursor.fetchall()]
        if "email" not in reg_cols:
            try: db.execute("ALTER TABLE registrations ADD COLUMN email TEXT")
            except Exception: pass
        if "face_registered" not in reg_cols:
            try: db.execute("ALTER TABLE registrations ADD COLUMN face_registered INTEGER DEFAULT 0")
            except Exception: pass
        if "samples_count" not in reg_cols:
            try: db.execute("ALTER TABLE registrations ADD COLUMN samples_count INTEGER DEFAULT 0")
            except Exception: pass
        if "current_zone" not in reg_cols:
            try: db.execute("ALTER TABLE registrations ADD COLUMN current_zone TEXT DEFAULT 'Pending'")
            except Exception: pass
        if "risk_level" not in reg_cols:
            try: db.execute("ALTER TABLE registrations ADD COLUMN risk_level TEXT DEFAULT 'LOW'")
            except Exception: pass

        # Migration helper for visitor_face_embeddings
        cursor = db.execute("PRAGMA table_info(visitor_face_embeddings)")
        vfe_cols = [row[1] for row in cursor.fetchall()]
        if "samples_count" not in vfe_cols:
            try: db.execute("ALTER TABLE visitor_face_embeddings ADD COLUMN samples_count INTEGER DEFAULT 1")
            except Exception: pass

        # Migration helper for locations
        try:
            cursor = db.execute("PRAGMA table_info(locations)")
            loc_cols = [row[1] for row in cursor.fetchall()]
            if "unique_id" not in loc_cols:
                db.execute("ALTER TABLE locations ADD COLUMN unique_id TEXT")
            if "altitude" not in loc_cols:
                db.execute("ALTER TABLE locations ADD COLUMN altitude REAL")
            if "heading" not in loc_cols:
                db.execute("ALTER TABLE locations ADD COLUMN heading REAL")
            if "speed" not in loc_cols:
                db.execute("ALTER TABLE locations ADD COLUMN speed REAL")
        except Exception:
            pass


def extract_standard_face_crop(img_bgr: np.ndarray, fx: int, fy: int, fw: int, fh: int, pad_ratio: float = 0.0) -> np.ndarray:
    """Extracts a standardized face crop with consistent scale between registration and detection."""
    ih, iw = img_bgr.shape[:2]
    pw = int(fw * pad_ratio)
    ph = int(fh * pad_ratio)
    x1 = max(0, fx - pw)
    y1 = max(0, fy - ph)
    x2 = min(iw, fx + fw + pw)
    y2 = min(ih, fy + fh + ph)
    return img_bgr[y1:y2, x1:x2]


def reload_embeddings_cache():
    """
    Loads all active enrolled face embeddings from SQLite into memory.
    Key properties:
      1. Internal identity is UNIQUE_ID (not name).
      2. Profiles with status == 'Disabled' are strictly omitted from active recognition.
      3. Loads both L2-normalized centroid and multi-photo enrollment samples.
    """
    global REGISTERED_EMBEDDINGS_CACHE
    try:
        with db_conn(True) as db:
            rows = db.execute("""
                SELECT vfe.id, vfe.unique_id, vfe.name, vfe.embedding, vfe.face_thumbnail, r.status
                FROM visitor_face_embeddings vfe
                LEFT JOIN registrations r ON vfe.unique_id = r.unique_id
                ORDER BY vfe.id DESC
            """).fetchall()

            # Check if visitor_face_samples table exists and load individual sample embeddings
            samples_by_uid = {}
            has_samples_tbl = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='visitor_face_samples'").fetchone()
            if has_samples_tbl:
                s_rows = db.execute("SELECT unique_id, embedding FROM visitor_face_samples ORDER BY id ASC").fetchall()
                for sr in s_rows:
                    uid = sr["unique_id"]
                    if sr["embedding"]:
                        s_emb = np.frombuffer(sr["embedding"], dtype=np.float32)
                        s_norm = np.linalg.norm(s_emb)
                        if s_norm > 0:
                            samples_by_uid.setdefault(uid, []).append(s_emb / s_norm)

            cache = []
            seen_uids = set()
            for r in rows:
                uid = r["unique_id"]
                if not uid or uid in seen_uids:
                    continue

                status = (r["status"] or "Active").strip()
                # If disabled, do not include in live recognition cache
                if status.lower() == "disabled":
                    continue

                raw_name = (r["name"] or "Unknown").strip()
                if r["embedding"]:
                    emb = np.frombuffer(r["embedding"], dtype=np.float32)
                    norm = np.linalg.norm(emb)
                    if norm > 0:
                        centroid = emb / norm
                        samples = samples_by_uid.get(uid, [centroid])
                        cache.append({
                            "unique_id": uid,
                            "name": raw_name,
                            "status": status,
                            "centroid": centroid,
                            "samples": samples,
                            "samples_count": len(samples),
                            "thumbnail": r["face_thumbnail"] or ""
                        })
                        seen_uids.add(uid)
            REGISTERED_EMBEDDINGS_CACHE = cache
    except Exception as e:
        print(f"[reload_embeddings_cache error]: {e}")
        REGISTERED_EMBEDDINGS_CACHE = []


def register_face_biometrics_multi(
    images_b64: List[str],
    unique_id: str,
    name: str
) -> Tuple[Optional[bytes], str, int, Optional[str]]:
    """
    Enrolls 1 to 5 real photographic images for a registered visitor:
    1. Validates real photographs.
    2. Stores real photographs under dataset/faces/<unique_id>/face_01.jpg ... face_05.jpg.
    3. Computes 128-D embedding via custom ForestFaceIdentifier for each sample.
    4. Computes normalized centroid prototype across all sample embeddings.
    5. Stores sample embeddings and centroid in database.
    6. Refreshes active in-memory recognition cache.
    """
    from backend.app.ai import get_face_identifier
    identifier = get_face_identifier()

    if not images_b64:
        return None, "", 0, "No face images provided"

    enrollment_dir = os.path.join(project_root, "dataset", "faces", unique_id)

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
                return None, "", 0, f"Photo capture failed for sample #{idx+1}: {reason}"

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

        # Save authentic photograph crop to dataset/faces/<unique_id>/face_{idx+1:02d}.jpg
        os.makedirs(enrollment_dir, exist_ok=True)
        sample_filename = f"face_{idx+1:02d}.jpg"
        sample_path = os.path.join(enrollment_dir, sample_filename)
        cv2.imwrite(sample_path, face_crop)

        rel_path = f"dataset/faces/{unique_id}/{sample_filename}"
        saved_samples.append((idx + 1, rel_path, normalized_emb.tobytes()))

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
        return None, "", 0, "No valid faces could be extracted from the provided photographs."

    # Filter out isolated outlier samples (e.g. camera motion blur, dark frames, or different person)
    if len(valid_embeddings) >= 3:
        filtered_embs = []
        for i, e_i in enumerate(valid_embeddings):
            other_sims = [float(np.dot(e_i, e_j)) for j, e_j in enumerate(valid_embeddings) if j != i]
            mean_sim = float(np.mean(other_sims)) if other_sims else 1.0
            if mean_sim >= 0.60:  # Must be strongly consistent with the person's facial samples
                filtered_embs.append(e_i)
        if len(filtered_embs) >= 2:
            valid_embeddings = filtered_embs

    # Compute L2-normalized centroid prototype across all consistent samples
    centroid = np.mean(valid_embeddings, axis=0)
    c_norm = np.linalg.norm(centroid)
    if c_norm > 0:
        centroid = centroid / c_norm
    centroid_bytes = centroid.astype(np.float32).tobytes()

    with db_conn() as db:
        db.execute("""
            INSERT OR REPLACE INTO visitor_face_embeddings
            (unique_id, name, embedding, face_thumbnail, samples_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (unique_id, name, sqlite3.Binary(centroid_bytes), first_thumb_b64, len(valid_embeddings), now_str))

        try:
            db.execute("DELETE FROM visitor_face_samples WHERE unique_id = ?", (unique_id,))
            for s_idx, s_path, s_emb_bytes in saved_samples:
                db.execute("""
                    INSERT INTO visitor_face_samples
                    (unique_id, sample_index, image_path, embedding, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (unique_id, s_idx, s_path, sqlite3.Binary(s_emb_bytes), now_str))
        except Exception as e:
            print(f"[register_face_biometrics_multi db error]: {e}")

        db.execute("""
            UPDATE registrations
            SET face_registered = 1, samples_count = ?
            WHERE unique_id = ?
        """, (len(valid_embeddings), unique_id))

    reload_embeddings_cache()
    return centroid_bytes, first_thumb_b64, len(valid_embeddings), None


def register_face_biometric(image_b64: str, unique_id: Optional[str] = None, name: str = "") -> Tuple[Optional[bytes], str, Optional[str]]:
    """
    Single-photo enrollment wrapper for backward compatibility.
    If unique_id is provided, delegates to multi-photo pipeline and writes to disk.
    """
    if unique_id:
        emb_bytes, thumb_b64, count, err = register_face_biometrics_multi([image_b64], unique_id, name)
        return emb_bytes, thumb_b64, err

    from backend.app.ai import get_face_identifier
    identifier = get_face_identifier()

    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]

    try:
        img_bytes = base64.b64decode(image_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return None, "", "Could not decode provided image"
    except Exception as e:
        return None, "", f"Image decode error: {e}"

    # Strict real photograph validation
    is_real, reason = validate_real_photograph(img, min_width=100, min_height=100, is_pre_cropped=True)
    if not is_real:
        return None, "", f"Photo capture failed: {reason}"

    # Pure custom face localization
    face_crop, bbox = custom_localize_face(img)
    if face_crop is None or face_crop.size == 0:
        face_crop = cv2.resize(img, (112, 112), interpolation=cv2.INTER_AREA)

    embedding = identifier.get_embedding(face_crop)
    if embedding is None:
        return None, "", "Face embedding computation failed"

    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm

    embedding_bytes = embedding.astype(np.float32).tobytes()

    thumb = cv2.resize(face_crop, (100, 100))
    _, enc = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 85])
    thumb_b64 = f"data:image/jpeg;base64,{base64.b64encode(enc).decode('utf-8')}"

    return embedding_bytes, thumb_b64, None


def delete_registered_visitor(unique_id: str) -> Dict[str, Any]:
    """
    Completely purges a visitor:
      1. Delete visitor record from registrations table.
      2. Delete face centroid from visitor_face_embeddings table.
      3. Delete individual face samples from visitor_face_samples table.
      4. Delete recognition events from recognition_events table.
      5. Delete SOS alerts from sos_alerts table.
      6. Delete location history from locations table.
      7. Purge canonical User and FaceProfile records from SQLAlchemy users table.
      8. Remove enrollment photographs directory from disk (dataset/faces/<unique_id>).
      9. Clear in-memory zone tracking state.
      10. Invalidate and reload active recognition cache.
    """
    global VISITOR_ZONE_STATE
    unique_id = (unique_id or "").strip()
    if not unique_id:
        return {"success": False, "error": "Missing or invalid unique_id"}

    with db_conn() as db:
        db.execute("DELETE FROM registrations WHERE unique_id = ?", (unique_id,))
        db.execute("DELETE FROM visitor_face_embeddings WHERE unique_id = ?", (unique_id,))
        try: db.execute("DELETE FROM visitor_face_samples WHERE unique_id = ?", (unique_id,))
        except Exception: pass
        try: db.execute("DELETE FROM recognition_events WHERE unique_id = ?", (unique_id,))
        except Exception: pass
        try: db.execute("DELETE FROM sos_alerts WHERE unique_id = ?", (unique_id,))
        except Exception: pass
        try: db.execute("DELETE FROM locations WHERE unique_id = ?", (unique_id,))
        except Exception: pass

        # Also purge from users and face_profiles tables
        try:
            db.execute("DELETE FROM face_profiles WHERE user_id IN (SELECT id FROM users WHERE forest_user_id = ?)", (unique_id,))
            db.execute("DELETE FROM users WHERE forest_user_id = ?", (unique_id,))
        except Exception as e:
            print(f"[delete_registered_visitor users table purge error]: {e}")

    # Remove enrollment photos from disk
    enrollment_dir = os.path.join(project_root, "dataset", "faces", unique_id)
    if os.path.exists(enrollment_dir) and os.path.isdir(enrollment_dir):
        try:
            shutil.rmtree(enrollment_dir)
        except Exception as e:
            print(f"[delete_registered_visitor] Error removing disk dir {enrollment_dir}: {e}")

    # Remove zone state
    if unique_id in VISITOR_ZONE_STATE:
        del VISITOR_ZONE_STATE[unique_id]

    # Invalidate and reload recognition cache
    reload_embeddings_cache()

    return {"success": True, "unique_id": unique_id}


def toggle_visitor_status(unique_id: str) -> Dict[str, Any]:
    """
    Toggles a registered person's status between 'Active' and 'Disabled'.
    Disabled profiles remain in database records for audit, but their embeddings
    are excluded from the live recognition cache so they cannot be identified.
    """
    unique_id = (unique_id or "").strip()
    with db_conn(True) as db:
        row = db.execute("SELECT status FROM registrations WHERE unique_id = ?", (unique_id,)).fetchone()
        if not row:
            return {"success": False, "error": f"Visitor {unique_id} not found"}
        current_status = row["status"] or "Active"
        new_status = "Disabled" if current_status.lower() == "active" else "Active"
        db.execute("UPDATE registrations SET status = ? WHERE unique_id = ?", (new_status, unique_id))

    reload_embeddings_cache()
    return {"success": True, "unique_id": unique_id, "new_status": new_status}


def record_gps_update_with_geofence(
    unique_id: str,
    latitude: float,
    longitude: float,
    accuracy: float = 0.0,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Evaluates real GPS coordinates against Forest Zones using Shapely Point-in-Polygon:
    1. Validates coordinates.
    2. Runs Point-in-Polygon via GeofenceService.
    3. Detects zone state changes and applies 15-second alert cooldown.
    4. Updates visitor's current location in registrations table.
    5. Appends record to locations history table.
    6. Triggers high/critical alerts when appropriate.
    """
    global VISITOR_ZONE_STATE
    from backend.app.services.geofence_service import GeofenceService

    # 1. Validation
    if latitude is None or longitude is None:
        return {"success": False, "error": "Latitude and longitude required"}
    try:
        lat = float(latitude)
        lon = float(longitude)
        acc = float(accuracy or 0.0)
    except (ValueError, TypeError):
        return {"success": False, "error": "Invalid numeric coordinates"}

    if not (-90.0 <= lat <= 90.0):
        return {"success": False, "error": f"Latitude out of bounds: {lat}"}
    if not (-180.0 <= lon <= 180.0):
        return {"success": False, "error": f"Longitude out of bounds: {lon}"}

    # 2. Run Point-in-Polygon
    zone_info = GeofenceService.check_location_risk(lat, lon)
    curr_risk = zone_info.get("risk_level", "LOW")
    curr_zone_name = zone_info.get("zone_name", "General Forest Buffer")
    curr_zone_code = zone_info.get("zone_code", "GENERAL-BUFFER")
    zone_id = zone_info.get("zone_id")

    # 3. Zone State Change & Alert Cooldown
    prev_state = VISITOR_ZONE_STATE.get(unique_id, {
        "last_zone_code": "OUTSIDE",
        "last_risk_level": "LOW",
        "last_alert_time": 0.0
    })
    prev_risk = prev_state["last_risk_level"]
    prev_zone_code = prev_state["last_zone_code"]
    last_alert_time = prev_state["last_alert_time"]
    now_ts = time.time()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    alert_triggered = False
    alert_details = None

    if curr_risk in ["HIGH", "CRITICAL"]:
        entered_new_restricted = (prev_risk not in ["HIGH", "CRITICAL"]) or (prev_zone_code != curr_zone_code)
        escalated_risk = (prev_risk == "HIGH" and curr_risk == "CRITICAL")
        cooldown_elapsed = (now_ts - last_alert_time) >= GEOFENCE_ALERT_COOLDOWN_SECONDS

        if entered_new_restricted or escalated_risk or cooldown_elapsed:
            alert_triggered = True
            severity = "HIGH" if curr_risk == "CRITICAL" else "MEDIUM"
            alert_details = f"Geo-fence Warning: Visitor [{unique_id}] entered {curr_risk} Risk Zone: {curr_zone_name} ({curr_zone_code})"

            # Insert alert event
            with db_conn() as db:
                db.execute("""
                    INSERT INTO events (timestamp, event_type, people, zone, confidence, details)
                    VALUES (?, 'GEOFENCE_RESTRICTED_ALERT', 1, ?, 1.0, ?)
                """, (now_str, curr_risk, alert_details))

                try:
                    db.execute("""
                        INSERT INTO alerts (alert_type, severity, user_id, zone_id, latitude, longitude, message, is_resolved, created_at)
                        VALUES ('GEOFENCE_WARNING', ?, ?, ?, ?, ?, ?, 0, ?)
                    """, (severity, user_id or 1, zone_id, lat, lon, alert_details, now_str))
                except Exception:
                    pass

            last_alert_time = now_ts

    # Update state tracking
    VISITOR_ZONE_STATE[unique_id] = {
        "last_zone_code": curr_zone_code,
        "last_risk_level": curr_risk,
        "last_alert_time": last_alert_time
    }

    # 4. Update registrations table current location
    with db_conn() as db:
        db.execute("""
            UPDATE registrations
            SET latitude = ?, longitude = ?, gps_status = 'Active', last_active = ?, current_zone = ?, risk_level = ?
            WHERE unique_id = ?
        """, (lat, lon, now_str, curr_zone_name, curr_risk, unique_id))

        # 5. Append to locations history table
        try:
            db.execute("""
                INSERT INTO locations (unique_id, user_id, latitude, longitude, zone_id, accuracy, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (unique_id, user_id or 1, lat, lon, zone_id, acc, now_str))
        except Exception as e:
            print(f"[record_gps_update_with_geofence locations insert]: {e}")

    # Broadcast real-time location and geofence alerts to connected officers
    try:
        from backend.app.services.notification_service import NotificationService
        v_name = unique_id
        with db_conn(True) as db:
            v_row = db.execute("SELECT name FROM registrations WHERE unique_id = ?", (unique_id,)).fetchone()
            if v_row and v_row["name"]:
                v_name = v_row["name"]

        NotificationService.broadcast_location_update({
            "unique_id": unique_id,
            "user_id": user_id or unique_id,
            "name": v_name,
            "latitude": lat,
            "longitude": lon,
            "accuracy": acc,
            "current_zone": curr_zone_name,
            "zone_code": curr_zone_code,
            "risk_level": curr_risk,
            "is_restricted": curr_risk in ["HIGH", "CRITICAL"],
            "alert_triggered": alert_triggered,
            "timestamp": now_str
        })

        if alert_triggered:
            NotificationService.broadcast_alert({
                "alert_type": "GEOFENCE_WARNING",
                "severity": severity,
                "user_id": user_id or 1,
                "unique_id": unique_id,
                "name": v_name,
                "zone_id": zone_id,
                "zone_name": curr_zone_name,
                "zone_code": curr_zone_code,
                "risk_level": curr_risk,
                "latitude": lat,
                "longitude": lon,
                "message": alert_details,
                "timestamp": now_str
            })
    except Exception as e:
        print(f"[record_gps_update_with_geofence broadcast warning]: {e}")

    return {
        "success": True,
        "unique_id": unique_id,
        "latitude": lat,
        "longitude": lon,
        "zone_code": curr_zone_code,
        "zone_name": curr_zone_name,
        "risk_level": curr_risk,
        "zone": {
            "id": zone_id,
            "name": curr_zone_name,
            "code": curr_zone_code,
            "risk_level": curr_risk,
            "description": zone_info.get("description", ""),
            "is_restricted": zone_info.get("is_restricted", False)
        },
        "alert_triggered": alert_triggered,
        "alert_details": alert_details
    }



# Simple IoU tracker to maintain stable IDs across live frames
class SimpleTracker:
    def __init__(self, iou_thresh=0.3, max_age=8):
        self.iou_thresh = iou_thresh
        self.max_age = max_age
        self.tracks = {}
        self.next_id = 1

    def update(self, detected_boxes: List[List[int]]) -> List[int]:
        assigned_ids = []
        unmatched_dets = list(range(len(detected_boxes)))

        # Age active tracks
        for tid in list(self.tracks.keys()):
            self.tracks[tid]["age"] += 1
            if self.tracks[tid]["age"] > self.max_age:
                del self.tracks[tid]

        # Match existing tracks by IoU
        for tid, tdata in self.tracks.items():
            tbox = tdata["bbox"]
            best_iou = 0.0
            best_det_idx = None

            for d_idx in unmatched_dets:
                dbox = detected_boxes[d_idx]
                # compute IoU
                x1 = max(tbox[0], dbox[0])
                y1 = max(tbox[1], dbox[1])
                x2 = min(tbox[2], dbox[2])
                y2 = min(tbox[3], dbox[3])
                inter = max(0, x2 - x1) * max(0, y2 - y1)
                a1 = (tbox[2] - tbox[0]) * (tbox[3] - tbox[1])
                a2 = (dbox[2] - dbox[0]) * (dbox[3] - dbox[1])
                union = a1 + a2 - inter
                iou = inter / union if union > 0 else 0.0

                if iou > best_iou:
                    best_iou = iou
                    best_det_idx = d_idx

            if best_det_idx is not None and best_iou >= self.iou_thresh:
                self.tracks[tid]["bbox"] = detected_boxes[best_det_idx]
                self.tracks[tid]["age"] = 0
                unmatched_dets.remove(best_det_idx)
                assigned_ids.append((best_det_idx, tid))

        # Assign new IDs to remaining detections
        for d_idx in unmatched_dets:
            tid = self.next_id
            self.next_id += 1
            self.tracks[tid] = {"bbox": detected_boxes[d_idx], "age": 0}
            assigned_ids.append((d_idx, tid))

        assigned_ids.sort(key=lambda x: x[0])
        return [tid for _, tid in assigned_ids]

    def reset(self):
        self.tracks.clear()
        self.next_id = 1


TRACKER = SimpleTracker()


MATCH_THRESHOLD = 0.78  # Calibrated for ForestFaceNet (same person >= 0.85, strangers <= 0.72)
MIN_CENTROID_SIM = 0.75  # Strict Centroid Prototype Correlation Gate


def process_detection_frame(frame_bgr: np.ndarray) -> Dict[str, Any]:
    """
    Runs custom ForestPersonDetector and ForestFaceIdentifier on an incoming frame with
    Face-Person Harmonization.
    Guarantees:
      1. 1-to-1 Unique Identity Assignment: No two persons in the same frame will EVER share the same registered identity or name.
      2. If a person does not match an enrolled visitor with high confidence (>= 0.60), they are explicitly labeled 'UNREGISTERED'.
      3. Strict Face Verification: Only targets with a verified human face are eligible for biometric matching.
      4. Close-Up & Webcam Support: Automatically harmonizes face detections with body detections, ensuring
         laptop webcams and close-up checkpoint cameras reliably detect and identify persons.
    """
    global LAST_INTRUSION_TIMES
    from backend.app.ai import get_person_detector, get_face_identifier

    detector = get_person_detector()
    identifier = get_face_identifier()

    h, w = frame_bgr.shape[:2]

    # 1. Global Face Detection using OpenCV Haar Cascade
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    gray_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    raw_faces = face_cascade.detectMultiScale(
        gray_frame, scaleFactor=1.06, minNeighbors=2, minSize=(24, 24)
    )

    # Filter out impossible oversized face boxes (e.g. > 40% frame dimension) and deduplicate
    max_fw = int(w * 0.40)
    max_fh = int(h * 0.50)
    valid_raw_faces = [
        (int(fx), int(fy), int(fw), int(fh))
        for (fx, fy, fw, fh) in raw_faces
        if fw <= max_fw and fh <= max_fh and fw >= 24 and fh >= 24
    ]

    # Deduplicate overlapping / nested face bounding boxes (Non-Maximum Suppression)
    global_faces = []
    if valid_raw_faces:
        sorted_faces = sorted(valid_raw_faces, key=lambda f: abs(f[2] - f[3]))
        for fx, fy, fw, fh in sorted_faces:
            fcx = fx + fw / 2.0
            fcy = fy + fh / 2.0
            fa = fw * fh
            dup = False
            for cfx, cfy, cfw, cfh in global_faces:
                cfcx = cfx + cfw / 2.0
                cfcy = cfy + cfh / 2.0
                dist = np.hypot(fcx - cfcx, fcy - cfcy)
                min_dim = min(fw, cfw, fh, cfh)
                # If face centers are closer than 1.8x face dimension, they belong to the same person's head
                if dist < 1.8 * min_dim:
                    dup = True
                    break
                cfa = cfw * cfh
                ix1 = max(fx, cfx)
                iy1 = max(fy, cfy)
                ix2 = min(fx + fw, cfx + cfw)
                iy2 = min(fy + fh, cfy + cfh)
                inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                min_a = min(fa, cfa)
                if min_a > 0 and (inter / float(min_a)) > 0.35:
                    dup = True
                    break
            if not dup:
                global_faces.append((fx, fy, fw, fh))

    # 2. Person Detection via ForestPersonDetector
    det_result = detector.detect(frame_bgr)
    raw_detections = det_result.get("detections", [])
    raw_boxes = [d["bbox"] for d in raw_detections]
    raw_confs = [d["confidence"] for d in raw_detections]

    # 3. Face-Person Harmonization
    targets = []
    claimed_raw = set()

    for fx, fy, fw, fh in global_faces:
        fcx = fx + fw / 2.0
        fcy = fy + fh / 2.0

        overlapping = []
        for bi, (bx1, by1, bx2, by2) in enumerate(raw_boxes):
            bw = max(1, bx2 - bx1)
            bh = max(1, by2 - by1)
            x_left = max(bx1, fx)
            x_right = min(bx2, fx + fw)
            overlap_w = max(0, x_right - x_left)
            if overlap_w >= 0.20 * min(bw, fw) and (by1 - 0.25 * bh) <= fcy <= (by1 + 0.90 * bh):
                overlapping.append(bi)
                claimed_raw.add(bi)

        if overlapping:
            # Merge overlapping body slivers with the face
            all_x1 = min([raw_boxes[bi][0] for bi in overlapping] + [fx - int(fw * 0.25)])
            all_y1 = min([raw_boxes[bi][1] for bi in overlapping] + [fy - int(fh * 0.15)])
            all_x2 = max([raw_boxes[bi][2] for bi in overlapping] + [fx + fw + int(fw * 0.25)])
            all_y2 = max([raw_boxes[bi][3] for bi in overlapping] + [fy + fh + int(fh * 2.50)])
            bbox = [max(0, int(all_x1)), max(0, int(all_y1)), min(w, int(all_x2)), min(h, int(all_y2))]
            conf = max([raw_confs[bi] for bi in overlapping])
        else:
            # Close-up webcam / checkpoint portrait: construct natural person bounding box around face
            bbox = [
                max(0, int(fx - fw * 0.35)),
                max(0, int(fy - fh * 0.15)),
                min(w, int(fx + fw * 1.35)),
                min(h, int(fy + fh * 2.80))
            ]
            conf = 0.95

        fcrop = extract_standard_face_crop(frame_bgr, fx, fy, fw, fh, pad_ratio=0.0)
        targets.append({
            "bbox": bbox,
            "face_crop": fcrop,
            "confidence": conf
        })

    # Add distant person detections where no global face was resolved
    for bi, (bx1, by1, bx2, by2) in enumerate(raw_boxes):
        if bi in claimed_raw:
            continue
        bw = bx2 - bx1
        bh = by2 - by1
        # Suppress degenerate narrow background slivers
        if bw < 28 and (bw / max(1, bh)) < 0.22:
            continue

        # Check if this raw box is already largely contained within an existing face-harmonized target
        is_sub_box = False
        area_b = bw * bh
        for t in targets:
            tx1, ty1, tx2, ty2 = t["bbox"]
            ix1 = max(bx1, tx1)
            iy1 = max(by1, ty1)
            ix2 = min(bx2, tx2)
            iy2 = min(by2, ty2)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            if area_b > 0 and (inter / area_b) > 0.60:
                is_sub_box = True
                break
        if is_sub_box:
            continue

        # Secondary search in upper 45% head region for distant face
        dist_face_crop = None
        head_y1 = max(0, by1)
        head_y2 = min(h, by1 + int(bh * 0.45))
        head_x1 = max(0, bx1)
        head_x2 = min(w, bx2)
        head_bgr = frame_bgr[head_y1:head_y2, head_x1:head_x2]
        if head_bgr.size > 0 and min(head_bgr.shape[:2]) >= 20:
            hgray = cv2.cvtColor(head_bgr, cv2.COLOR_BGR2GRAY)
            l_faces = face_cascade.detectMultiScale(
                hgray, scaleFactor=1.05, minNeighbors=2, minSize=(18, 18)
            )
            if len(l_faces) > 0:
                lfx, lfy, lfw, lfh = max(l_faces, key=lambda f: f[2] * f[3])
                dist_face_crop = extract_standard_face_crop(head_bgr, lfx, lfy, lfw, lfh, pad_ratio=0.0)
            else:
                c_crop, _ = custom_localize_face(head_bgr)
                if c_crop is not None and c_crop.size > 0:
                    dist_face_crop = c_crop

        targets.append({
            "bbox": [int(bx1), int(by1), int(bx2), int(by2)],
            "face_crop": dist_face_crop,
            "confidence": raw_confs[bi]
        })

    # Deduplicate overlapping person targets (NMS)
    if len(targets) > 1:
        clean_targets = []
        sorted_targets = sorted(targets, key=lambda t: (1 if t.get("face_crop") is not None else 0, t["confidence"]), reverse=True)
        for t in sorted_targets:
            bx1, by1, bx2, by2 = t["bbox"]
            area_b = max(1, (bx2 - bx1) * (by2 - by1))
            overlap = False
            for ct in clean_targets:
                cx1, cy1, cx2, cy2 = ct["bbox"]
                ix1 = max(bx1, cx1)
                iy1 = max(by1, cy1)
                ix2 = min(bx2, cx2)
                iy2 = min(by2, cy2)
                inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                if (inter / float(area_b)) > 0.40:
                    overlap = True
                    break
            if not overlap:
                clean_targets.append(t)
        targets = clean_targets

    # 4. Extract Embeddings for targets with verified faces
    target_embeddings = {}
    for ti, t in enumerate(targets):
        fc = t.get("face_crop")
        if fc is not None and fc.size > 0:
            emb = identifier.get_embedding(fc)
            if emb is not None:
                norm = np.linalg.norm(emb)
                if norm > 0:
                    target_embeddings[ti] = emb / norm

    # 5. Person-Specific Face Recognition with Centroid Prototype, Margin Validation & 1-to-1 Unique ID Locking
    assigned_matches = {}  # target_idx -> {"visitor_name": ..., "visitor_id": ..., "match_confidence": ..., "second_similarity": ..., "margin": ...}
    used_visitor_ids = set()
    used_names = set()

    if len(REGISTERED_EMBEDDINGS_CACHE) > 0 and len(target_embeddings) > 0:
        eligible_matches = []

        # For every detected face query, independently evaluate against all active registered profiles
        for ti, t_emb in target_embeddings.items():
            candidates = []
            for reg in REGISTERED_EMBEDDINGS_CACHE:
                centroid_sim = float(np.dot(t_emb, reg["centroid"]))
                # Strict prototype gate: query face MUST correlate strongly with the profile centroid
                if centroid_sim < MIN_CENTROID_SIM:
                    continue

                sample_sims = [float(np.dot(t_emb, s)) for s in reg.get("samples", [])]
                top_samples = sorted(sample_sims, reverse=True)[:3]
                top_sample_sim = float(np.mean(top_samples)) if top_samples else centroid_sim
                # Balanced metric: 60% centroid baseline + 40% top multi-pose sample match
                best_profile_sim = 0.60 * centroid_sim + 0.40 * top_sample_sim

                candidates.append({
                    "unique_id": reg["unique_id"],
                    "name": reg["name"],
                    "similarity": best_profile_sim,
                    "centroid_sim": centroid_sim
                })

            if not candidates:
                continue

            # Sort candidate matches in descending order of similarity
            candidates.sort(key=lambda x: x["similarity"], reverse=True)
            best_candidate = candidates[0]
            # Second candidate represents the top competing DIFFERENT identity (not duplicate profiles of same person)
            second_candidate = next(
                (c for c in candidates[1:] if c["name"].strip().lower() != best_candidate["name"].strip().lower()),
                None
            )

            best_sim = best_candidate["similarity"]
            second_sim = second_candidate["similarity"] if second_candidate else 0.0
            margin = best_sim - second_sim

            # Conservative Verification:
            # 1. Best similarity must exceed MATCH_THRESHOLD (e.g. 0.50)
            # 2. Similarity margin over 2nd best must exceed MARGIN_THRESHOLD (e.g. 0.08)
            #    If margin is too narrow, the face is ambiguous and MUST remain UNREGISTERED / UNKNOWN!
            if best_sim >= MATCH_THRESHOLD:
                if second_candidate is None or margin >= MARGIN_THRESHOLD:
                    eligible_matches.append((best_sim, ti, best_candidate, second_sim, margin))

        # Frame-level 1-to-1 matching:
        # Sort eligible matches by highest similarity first and assign greedily
        # Strictly ensures NO two persons in the same frame will EVER share the same visitor ID or visitor name
        eligible_matches.sort(key=lambda x: x[0], reverse=True)
        for best_sim, ti, best_cand, second_sim, margin in eligible_matches:
            uid = best_cand["unique_id"]
            name = best_cand["name"]
            if ti not in assigned_matches and uid not in used_visitor_ids and name not in used_names:
                assigned_matches[ti] = {
                    "visitor_name": name,
                    "visitor_id": uid,
                    "match_confidence": best_sim,
                    "second_similarity": second_sim,
                    "margin": margin
                }
                used_visitor_ids.add(uid)
                used_names.add(name)

    # 6. Spatial Tracking and Zone Computation
    detected_boxes = [t["bbox"] for t in targets]
    track_ids = TRACKER.update(detected_boxes)

    zone_a_limit = w * 0.35
    zone_b_limit = w * 0.70

    people = []
    now_ts = time.time()
    now_str = datetime.now().strftime("%H:%M:%S")
    alerts_to_emit = []
    active_event_type = None

    for i, t in enumerate(targets):
        bbox = t["bbox"]
        tid = track_ids[i] if i < len(track_ids) else (i + 1)
        conf = t["confidence"]

        cx = (bbox[0] + bbox[2]) / 2.0
        if cx < zone_a_limit:
            zone = "A"
        elif cx < zone_b_limit:
            zone = "B"
        else:
            zone = "C"

        if i in assigned_matches:
            match_info = assigned_matches[i]
            status = "REGISTERED"
            visitor_name = match_info["visitor_name"]
            visitor_id = match_info["visitor_id"]
            match_confidence = round(match_info["match_confidence"], 3)
            second_similarity = round(match_info.get("second_similarity", 0.0), 3)
            margin = round(match_info.get("margin", 0.0), 3)
        else:
            status = "UNREGISTERED"
            visitor_name = "UNREGISTERED"
            visitor_id = "UNREGISTERED"
            match_confidence = 0.0
            second_similarity = 0.0
            margin = 0.0

        person_entry = {
            "track_id": tid,
            "bbox": bbox,
            "confidence": round(conf, 3),
            "zone": zone,
            "status": status,
            "visitor_name": visitor_name,
            "visitor_id": visitor_id,
            "match_confidence": match_confidence,
            "second_similarity": second_similarity,
            "margin": margin,
            "face_verified": (t.get("face_crop") is not None and t["face_crop"].size > 0)
        }
        people.append(person_entry)

        # Zone C Intrusion Alert Logic
        if zone == "C":
            last_alert = LAST_INTRUSION_TIMES.get(tid, 0.0)
            if now_ts - last_alert >= ALERT_COOLDOWN_SECONDS:
                LAST_INTRUSION_TIMES[tid] = now_ts

                if status == "REGISTERED":
                    event_type = "REGISTERED_RESTRICTED_WARNING"
                    details = f"Registered visitor in Zone C: {visitor_name} [{visitor_id}] (Track #{tid})"
                else:
                    event_type = "RESTRICTED_INTRUSION"
                    details = f"Restricted Zone C Intrusion: Track #{tid} (UNREGISTERED PERSON)"

                alerts_to_emit.append({
                    "event": event_type,
                    "track_id": tid,
                    "zone": "C",
                    "status": status,
                    "name": visitor_name,
                    "details": details
                })
                active_event_type = event_type

                with db_conn() as db:
                    db.execute(
                        "INSERT INTO events (timestamp, event_type, people, zone, confidence, details) VALUES (?, ?, ?, ?, ?, ?)",
                        (now_str, event_type, len(people), zone, conf, details)
                    )
                    db.execute(
                        "INSERT INTO recognition_events (tracking_id, unique_id, name, status, zone, confidence, details, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (tid, visitor_id, visitor_name, status, zone, match_confidence, details, now_str)
                    )

    # Dominant zone
    dominant_zone = "-"
    if people:
        dominant_zone = max(people, key=lambda p: p["confidence"])["zone"]

    registered_count = sum(1 for p in people if p["status"] == "REGISTERED")
    unregistered_count = sum(1 for p in people if p["status"] == "UNREGISTERED")
    registered_names = [p["visitor_name"] for p in people if p["status"] == "REGISTERED"]

    return {
        "width": int(w),
        "height": int(h),
        "people": people,
        "total_detected": len(people),
        "registered_count": registered_count,
        "unregistered_count": unregistered_count,
        "registered_names": registered_names,
        "is_single_person": len(people) == 1,
        "is_multiple_person": len(people) > 1,
        "unconfirmed_count": 0,
        "zone": dominant_zone,
        "restricted": any(p["zone"] == "C" for p in people),
        "event": active_event_type,
        "alerts": alerts_to_emit
    }


def reset_tracker():
    """Resets tracking IDs and alert cooldowns."""
    TRACKER.reset()
    LAST_INTRUSION_TIMES.clear()
