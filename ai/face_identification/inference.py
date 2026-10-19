import os
import json
import numpy as np
import torch
import cv2
from typing import Optional, Dict, Any
from ai.face_identification.model import ForestFaceNet
from ai.face_identification.preprocessing import detect_face_region, preprocess_face_for_model


class ForestFaceIdentifier:
    """
    Inference engine for ForestFaceNet face identification.
    Loads only project-trained weights from models/face_identifier.pth.
    """

    def __init__(
        self,
        model_path: str = "models/face_identifier.pth",
        class_map_path: str = "models/face_class_map.json",
        similarity_threshold: float = 0.65
    ):
        self.similarity_threshold = similarity_threshold
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.is_trained = False
        self.class_map = {}  # {str(idx): "person_001"}

        # Load class map (idx -> person folder name)
        if class_map_path and os.path.exists(class_map_path):
            with open(class_map_path, "r") as f:
                self.class_map = json.load(f)

        num_classes = len(self.class_map) if self.class_map else None

        # Build model
        self.model = ForestFaceNet(embedding_dim=128, num_classes=num_classes)
        if model_path and os.path.exists(model_path):
            try:
                state = torch.load(model_path, map_location=self.device)
                self.model.load_state_dict(state)
                self.is_trained = True
                print(f"[ForestFaceIdentifier] Loaded trained model from: {model_path}")
            except Exception as e:
                print(f"[ForestFaceIdentifier] Warning: Could not load checkpoint: {e}")
        else:
            print("[ForestFaceIdentifier] No trained model found. Face identification not available until trained.")

        self.model.to(self.device)
        self.model.eval()

    def get_embedding(self, face_bgr: np.ndarray) -> Optional[np.ndarray]:
        """Extracts 128-D L2-normalized embedding from a raw face crop."""
        try:
            face_tensor = preprocess_face_for_model(face_bgr)
            tensor = torch.from_numpy(face_tensor).unsqueeze(0).to(self.device)
            with torch.no_grad():
                embedding, _ = self.model(tensor)
            return embedding.squeeze(0).cpu().numpy()
        except Exception as e:
            print(f"[ForestFaceIdentifier.get_embedding Error]: {e}")
            return None

    def identify_from_stored_embeddings(
        self,
        query_embedding: np.ndarray,
        registered_profiles: list  # List of {"user_id": int, "user_name": str, "embedding": list}
    ) -> Dict[str, Any]:
        """
        Compares query face embedding against all registered user embeddings.
        Returns:
            Dict with keys: identity, user_id, similarity, status
        """
        if query_embedding is None:
            return {"identity": "NO_FACE", "user_id": None, "similarity": 0.0, "status": "NO_FACE_DETECTED"}

        if not registered_profiles:
            return {"identity": "Unknown Person", "user_id": None, "similarity": 0.0, "status": "NO_REGISTERED_USERS"}

        best_score = -1.0
        best_user_id = None
        best_name = None

        q = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)

        for profile in registered_profiles:
            stored_emb = np.array(profile.get("embedding", []), dtype=np.float32)
            if len(stored_emb) != 128:
                continue
            stored_emb = stored_emb / (np.linalg.norm(stored_emb) + 1e-8)
            score = float(np.dot(q, stored_emb))

            if score > best_score:
                best_score = score
                best_user_id = profile.get("user_id")
                best_name = profile.get("user_name", "Unknown")

        if best_score >= self.similarity_threshold:
            return {
                "identity": best_name,
                "user_id": best_user_id,
                "similarity": round(float(best_score), 4),
                "similarity_pct": round(float(best_score) * 100, 1),
                "status": "IDENTIFIED"
            }
        else:
            return {
                "identity": "Unknown Person",
                "user_id": None,
                "similarity": round(float(best_score), 4),
                "similarity_pct": round(float(best_score) * 100, 1),
                "status": "UNKNOWN_PERSON"
            }

    def identify_from_image(self, image_bgr: np.ndarray, registered_profiles: list) -> Dict[str, Any]:
        """Full pipeline: detect face ? extract embedding ? compare."""
        if not self.is_trained:
            return {"identity": "NOT_TRAINED", "user_id": None, "similarity": 0.0, "status": "MODEL_NOT_TRAINED"}

        face_crop, bbox = detect_face_region(image_bgr)
        if face_crop is None:
            return {"identity": "Unknown Person", "user_id": None, "similarity": 0.0, "status": "NO_FACE_DETECTED", "bbox": None}

        embedding = self.get_embedding(face_crop)
        result = self.identify_from_stored_embeddings(embedding, registered_profiles)
        result["bbox"] = bbox
        result["embedding"] = embedding.tolist() if embedding is not None else None
        return result
