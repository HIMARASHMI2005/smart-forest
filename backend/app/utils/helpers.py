import os
import re
import base64
import io
import numpy as np
import cv2
from PIL import Image
from flask import jsonify
from backend.app.extensions import db
from backend.app.models.log import SystemLog

def api_response(success: bool, message: str, data=None, status_code=200):
    """Standardized JSON API response structure."""
    payload = {
        "success": success,
        "message": message,
        "data": data if data is not None else {}
    }
    return jsonify(payload), status_code

def log_system_event(event_type: str, details: str = None):
    """Logs system events to database and console."""
    try:
        log_entry = SystemLog(event_type=event_type, details=details)
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[SystemLog Error]: {e}")

def decode_base64_image(base64_str: str) -> np.ndarray:
    """Decodes a base64 encoded data URI or raw string into an OpenCV BGR numpy image."""
    if not base64_str:
        return None
    
    # Strip data URI header if present (e.g. data:image/jpeg;base64,...)
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]
        
    image_bytes = base64.b64decode(base64_str)
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    return image

def encode_image_to_base64(image_np: np.ndarray, format: str = ".jpg") -> str:
    """Encodes an OpenCV numpy image into a base64 data URI."""
    if image_np is None:
        return ""
    success, buffer = cv2.imencode(format, image_np)
    if not success:
        return ""
    encoded_str = base64.b64encode(buffer).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded_str}"

def compute_cosine_similarity(vec_a, vec_b) -> float:
    """Calculates cosine similarity between two feature vectors."""
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
