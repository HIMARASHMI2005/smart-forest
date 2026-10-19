from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import numpy as np, base64, cv2
from backend.app.extensions import db
from backend.app.models import User, FaceProfile, Detection
from backend.app.services import NotificationService, GeofenceService
from backend.app.utils import api_response, decode_base64_image

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")


@ai_bp.route("/status", methods=["GET"])
def ai_status():
    """Returns current AI model training status."""
    import os
    person_path = current_app.config.get("PERSON_MODEL_PATH", "")
    face_path   = current_app.config.get("FACE_MODEL_PATH", "")
    return api_response(True, "AI Status", {
        "person_detector": {
            "status": "TRAINED" if os.path.exists(person_path) else "NOT_TRAINED",
            "model": "ForestPersonNet (Custom CNN - Random Init)",
            "checkpoint": os.path.basename(person_path) if os.path.exists(person_path) else None
        },
        "face_identifier": {
            "status": "TRAINED" if os.path.exists(face_path) else "NOT_TRAINED",
            "model": "ForestFaceNet (Custom Metric CNN - Random Init)",
            "checkpoint": os.path.basename(face_path) if os.path.exists(face_path) else None
        }
    })


@ai_bp.route("/detect", methods=["POST"])
@jwt_required()
def detect_persons():
    """
    Runs ForestPersonNet + ForestFaceNet on a base64 image frame.
    Returns bounding boxes, person count, face identities.
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        image_data = data.get("image")
        latitude   = data.get("latitude")
        longitude  = data.get("longitude")

        if not image_data:
            return api_response(False, "No image data provided.", status_code=400)

        frame = decode_base64_image(image_data)
        if frame is None:
            return api_response(False, "Failed to decode image.", status_code=422)

        # --- Person Detection ---
        from backend.app.ai import get_person_detector
        conf_thresh = float(current_app.config.get("PERSON_CONFIDENCE_THRESHOLD", 0.40))
        detector = get_person_detector(
            model_path=current_app.config.get("PERSON_MODEL_PATH"),
            conf_threshold=conf_thresh
        )
        det_result = detector.detect(frame)

        person_count = det_result["person_count"]
        detections   = det_result["detections"]
        is_model_trained = det_result.get("is_trained", False)

        # --- Face Identification ---
        from backend.app.ai import get_face_identifier
        sim_thresh = float(current_app.config.get("FACE_SIMILARITY_THRESHOLD", 0.65))
        identifier = get_face_identifier(
            model_path=current_app.config.get("FACE_MODEL_PATH"),
            similarity_threshold=sim_thresh
        )

        # Ensure class_name is always set on detections
        for d in detections:
            d["class_name"] = d.get("class") or d.get("class_name") or "person"
            d["class"] = d["class_name"]

        # Load all registered face profiles from FaceProfile and visitor cache
        profiles_db = FaceProfile.query.all()
        registered_profiles = []
        seen_names = set()
        for p in profiles_db:
            u = User.query.get(p.user_id)
            if u:
                registered_profiles.append({
                    "user_id": u.id,
                    "user_name": u.name,
                    "embedding": p.get_embedding()
                })
                seen_names.add(u.name.strip().lower())

        # Also pull from in-memory visitor cache
        try:
            from backend.app.services.visitor_service import REGISTERED_EMBEDDINGS_CACHE
            for reg in REGISTERED_EMBEDDINGS_CACHE:
                reg_name = (reg.get("name") or "").strip().lower()
                if reg_name and reg_name not in seen_names and reg.get("centroid") is not None:
                    c_emb = reg.get("centroid")
                    emb_list = c_emb.tolist() if hasattr(c_emb, "tolist") else list(c_emb)
                    registered_profiles.append({
                        "user_id": reg.get("unique_id"),
                        "user_name": reg.get("name"),
                        "embedding": emb_list
                    })
                    seen_names.add(reg_name)
        except Exception:
            pass

        faces_result = []
        is_unknown_detected = False

        if identifier.is_trained and person_count > 0:
            face_id_result = identifier.identify_from_image(frame, registered_profiles)
            faces_result.append(face_id_result)
            if face_id_result.get("status") == "UNKNOWN_PERSON":
                is_unknown_detected = True

        # --- Geo-fence Zone Check ---
        zone_info = {}
        if latitude and longitude:
            try:
                zone_info = GeofenceService.check_location_risk(float(latitude), float(longitude))
            except Exception:
                zone_info = {}

        # --- Risk Evaluation ---
        from backend.app.services.risk_engine import EmergencyRiskEngine
        risk = EmergencyRiskEngine.evaluate_risk(
            zone_risk_level=zone_info.get("risk_level", "LOW"),
            is_unknown_person=is_unknown_detected,
            person_count=person_count
        )

        # --- Persist Detection Event ---
        current_user_id = get_jwt_identity()
        identified_uid = None
        max_conf = max([d["confidence"] for d in detections], default=0.0)
        if faces_result and faces_result[0].get("status") == "IDENTIFIED":
            identified_uid = faces_result[0].get("user_id")

        det_record = Detection(
            person_count=person_count,
            identified_user_id=identified_uid,
            is_unknown=is_unknown_detected,
            confidence=max_conf,
            bounding_boxes=detections
        )
        db.session.add(det_record)
        db.session.commit()

        # --- Broadcast via SocketIO ---
        detection_payload = {
            "person_count": person_count,
            "is_unknown": is_unknown_detected,
            "risk_level": risk["level"],
            "latitude": latitude,
            "longitude": longitude
        }
        NotificationService.broadcast_detection(detection_payload)

        if is_unknown_detected:
            from backend.app.models.alert import Alert
            alert = Alert(
                alert_type="UNKNOWN_PERSON",
                severity="HIGH",
                latitude=latitude,
                longitude=longitude,
                message=f"Unidentified person detected (confidence: {max_conf:.0%}).",
                zone_id=zone_info.get("zone_id")
            )
            db.session.add(alert)
            db.session.commit()
            NotificationService.broadcast_alert(alert.to_dict())

        return api_response(True, "Detection complete.", {
            "person_count": person_count,
            "detections": detections,
            "faces": faces_result,
            "unknown_person_count": sum(1 for f in faces_result if f.get("status") == "UNKNOWN_PERSON"),
            "risk": risk,
            "zone": zone_info,
            "model_trained": is_model_trained
        })

    except Exception as e:
        db.session.rollback()
        return api_response(False, f"Detection error: {str(e)}", status_code=500)


@ai_bp.route("/register-face", methods=["POST"])
@jwt_required()
def register_face():
    """
    Accepts a base64 face image, extracts embedding via ForestFaceNet,
    and stores/updates the user's face profile in the database.
    """
    try:
        current_user_id = int(get_jwt_identity())
        user = User.query.get(current_user_id)
        if not user:
            return api_response(False, "User not found.", status_code=404)

        data = request.get_json(force=True, silent=True) or {}
        image_data = data.get("image")
        if not image_data:
            return api_response(False, "No face image provided.", status_code=400)

        frame = decode_base64_image(image_data)
        if frame is None:
            return api_response(False, "Invalid image data.", status_code=422)

        from backend.app.ai import get_face_identifier
        from ai.face_identification.preprocessing import detect_face_region
        identifier = get_face_identifier(model_path=current_app.config.get("FACE_MODEL_PATH"))

        if not identifier.is_trained:
            return api_response(False, "Face model not trained yet. Please train ForestFaceNet first.", status_code=503)

        face_crop, bbox = detect_face_region(frame)
        if face_crop is None:
            return api_response(False, "No face detected in the provided image. Please ensure your face is clearly visible.", status_code=422)

        embedding = identifier.get_embedding(face_crop)
        if embedding is None:
            return api_response(False, "Failed to extract face embedding.", status_code=500)

        # Save face image
        import os, uuid
        faces_dir = current_app.config.get("FACES_UPLOAD_FOLDER", "frontend/static/uploads/faces")
        os.makedirs(faces_dir, exist_ok=True)
        img_filename = f"user_{current_user_id}_{uuid.uuid4().hex[:8]}.jpg"
        img_path = os.path.join(faces_dir, img_filename)
        cv2.imwrite(img_path, face_crop)

        # Update or create face profile
        profile = FaceProfile.query.filter_by(user_id=current_user_id).first()
        if profile:
            # Average with existing embedding for robustness
            old_emb = np.array(profile.get_embedding(), dtype=np.float32)
            new_emb = (old_emb * profile.samples_count + embedding) / (profile.samples_count + 1)
            new_emb = new_emb / (np.linalg.norm(new_emb) + 1e-8)
            profile.embedding_vector = new_emb.tolist()
            profile.samples_count += 1
            profile.image_path = img_filename
        else:
            profile = FaceProfile(
                user_id=current_user_id,
                embedding_vector=embedding.tolist(),
                image_path=img_filename,
                samples_count=1
            )
            db.session.add(profile)

        db.session.commit()
        return api_response(True, "Face registered successfully.", {
            "samples_count": profile.samples_count,
            "image_path": img_filename
        })

    except Exception as e:
        db.session.rollback()
        return api_response(False, f"Face registration error: {str(e)}", status_code=500)
