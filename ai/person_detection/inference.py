import os
import torch
import torchvision.transforms as transforms
import numpy as np
import cv2
from PIL import Image
from typing import List, Dict, Any, Tuple
from ai.person_detection.model import ForestPersonNet

def compute_iou(box1: List[float], box2: List[float]) -> float:
    """Computes Intersection-over-Union (IoU) between two bounding boxes [x1, y1, x2, y2]."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])
    union = area1 + area2 - intersection

    if union <= 0.0:
        return 0.0
    return intersection / union

def non_max_suppression(boxes: List[Dict[str, Any]], iou_threshold: float = 0.45) -> List[Dict[str, Any]]:
    """Suppresses overlapping bounding boxes based on IoU threshold."""
    if not boxes:
        return []

    # Sort boxes by confidence in descending order
    boxes = sorted(boxes, key=lambda b: b["confidence"], reverse=True)
    kept_boxes = []

    while len(boxes) > 0:
        current = boxes.pop(0)
        kept_boxes.append(current)

        boxes = [
            b for b in boxes
            if compute_iou(current["bbox"], b["bbox"]) < iou_threshold
        ]

    return kept_boxes

class ForestPersonDetector:
    """
    Inference engine for custom ForestPersonNet.
    Runs fast CPU/GPU inference, box decoding, and NMS.
    """
    def __init__(self, model_path: str = "models/person_detector.pth", conf_threshold: float = 0.40, device: str = None):
        self.conf_threshold = conf_threshold
        self.device = torch.device(device if device else ("cuda" if torch.cuda.is_available() else "cpu"))
        self.img_size = 224
        self.grid_size = 7

        # Initialize network
        self.model = ForestPersonNet(grid_size=self.grid_size, num_classes=1)
        self.is_trained = False

        # Load weights if checkpoint exists
        if model_path and os.path.exists(model_path):
            try:
                state_dict = torch.load(model_path, map_location=self.device)
                self.model.load_state_dict(state_dict)
                self.is_trained = True
                print(f"[ForestPersonDetector] Loaded trained model from: {model_path}")
            except Exception as e:
                print(f"[ForestPersonDetector] Warning: Failed to load checkpoint {model_path}: {e}")
        else:
            print("[ForestPersonDetector] Initialized with random weights (Untrained / Training Mode).")

        self.model.to(self.device)
        self.model.eval()

        self.transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    def detect(self, image_input) -> Dict[str, Any]:
        """
        Detects persons in the given image.
        Args:
            image_input: OpenCV BGR image (numpy array) or PIL Image
        Returns:
            Dict containing person_count, detections list, and original image dimensions.
        """
        if isinstance(image_input, np.ndarray):
            orig_h, orig_w = image_input.shape[:2]
            image_rgb = cv2.cvtColor(image_input, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(image_rgb)
        elif isinstance(image_input, Image.Image):
            pil_img = image_input.convert("RGB")
            orig_w, orig_h = pil_img.size
        else:
            raise ValueError("Unsupported image input type. Expected numpy ndarray or PIL Image.")

        # Resize and preprocess
        resized_img = pil_img.resize((self.img_size, self.img_size))
        tensor = self.transform(resized_img).unsqueeze(0).to(self.device)

        with torch.no_grad():
            preds = self.model(tensor).squeeze(0)  # Shape: (S, S, 6)

        candidate_boxes = []
        S = self.grid_size

        for gy in range(S):
            for gx in range(S):
                tx = preds[gy, gx, 0].item()
                ty = preds[gy, gx, 1].item()
                tw = preds[gy, gx, 2].item()
                th = preds[gy, gx, 3].item()
                obj = preds[gy, gx, 4].item()
                cls_prob = preds[gy, gx, 5].item()

                confidence = obj * cls_prob

                if confidence >= self.conf_threshold:
                    # Convert cell-relative coordinates to image-relative [0, 1]
                    xc = (gx + tx) / S
                    yc = (gy + ty) / S

                    # Convert to absolute pixel coordinates [x1, y1, x2, y2]
                    x1 = max(0, int((xc - tw / 2.0) * orig_w))
                    y1 = max(0, int((yc - th / 2.0) * orig_h))
                    x2 = min(orig_w, int((xc + tw / 2.0) * orig_w))
                    y2 = min(orig_h, int((yc + th / 2.0) * orig_h))

                    # Filter invalid boxes
                    if (x2 - x1) >= 10 and (y2 - y1) >= 10:
                        candidate_boxes.append({
                            "bbox": [x1, y1, x2, y2],
                            "normalized_bbox": [round(x1 / orig_w, 4), round(y1 / orig_h, 4), round(x2 / orig_w, 4), round(y2 / orig_h, 4)],
                            "confidence": round(confidence, 4),
                            "class": "person"
                        })

        # Apply Non-Maximum Suppression
        final_detections = non_max_suppression(candidate_boxes, iou_threshold=0.45)

        return {
            "person_count": len(final_detections),
            "detections": final_detections,
            "image_width": orig_w,
            "image_height": orig_h,
            "is_trained": self.is_trained
        }
