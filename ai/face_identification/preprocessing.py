"""
Smart Forest Geo-Fence & Emergency Monitoring System
Custom Face Localization & Preprocessing (Strict No-Pretrained Architecture)

Provides:
1. custom_localize_face(): Pure geometric, anthropometric, and chrominance-based
   face localization designed for webcam framing. NO external XML, NO pretrained models.
2. preprocess_face_for_model(): Transforms a 112x112 face crop into a normalized
   (3, 112, 112) tensor for ForestFaceNet inference.
"""

import cv2
import numpy as np
from typing import Tuple, Optional, List
from PIL import Image

FACE_SIZE = 112  # Standardized input dimensions for ForestFaceNet
MEAN = [0.5, 0.5, 0.5]
STD = [0.5, 0.5, 0.5]


def custom_localize_face(image_bgr: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[List[int]]]:
    """
    Pure custom face localization without pretrained neural networks or Haar cascade XML.

    Combines:
    1. Webcam on-screen framing guidance bounds (upper-center oval).
    2. Anthropometric head-to-torso proportions.
    3. YCbCr / HSV dual-space skin chrominance segmentation.
    4. Morphological hole filling and noise reduction.
    5. Aspect ratio (1.0 to 1.9) and central proximity contour ranking.

    Returns:
        face_crop: Standardized 112x112 BGR numpy array, or None if invalid.
        bbox: [x, y, w, h] of localized face boundary in original image coords.
    """
    if image_bgr is None or not isinstance(image_bgr, np.ndarray) or image_bgr.size == 0:
        return None, None

    ih, iw = image_bgr.shape[:2]
    if ih < 40 or iw < 40:
        return None, None

    # If image is already a close-up cropped face/portrait (e.g. 112x112 or <= 160x160)
    aspect = float(ih) / float(max(1, iw))
    if iw <= 160 and ih <= 160 and 0.70 <= aspect <= 1.45:
        face_112 = cv2.resize(image_bgr, (FACE_SIZE, FACE_SIZE), interpolation=cv2.INTER_AREA)
        return face_112, [0, 0, iw, ih]

    # Default anthropometric upper-center framing oval region (guided by webcam UI)
    cx, cy = iw // 2, int(ih * 0.44)
    bw, bh = int(iw * 0.52), int(ih * 0.60)
    def_x = max(0, cx - bw // 2)
    def_y = max(0, cy - bh // 2)
    def_w = min(iw - def_x, bw)
    def_h = min(ih - def_y, bh)
    best_box = [def_x, def_y, def_w, def_h]

    try:
        # Dual-space human skin tone chrominance segmentation
        # YCbCr: Cr in [130, 175], Cb in [77, 130]
        ycbcr = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2YCrCb)
        cr = ycbcr[:, :, 1]
        cb = ycbcr[:, :, 2]
        mask_ycbcr = (cr >= 128) & (cr <= 178) & (cb >= 75) & (cb <= 135)

        # HSV: Hue in [0, 25] or [165, 180]
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        h_ch, s_ch, v_ch = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        mask_hsv = ((h_ch <= 25) | (h_ch >= 165)) & (s_ch >= 28) & (v_ch >= 40)

        combined_mask = (mask_ycbcr & mask_hsv).astype(np.uint8) * 255

        # Morphological operations to unite facial regions and suppress stray pixels
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        morphed = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel_close)
        morphed = cv2.morphologyEx(morphed, cv2.MORPH_OPEN, kernel_open)

        contours, _ = cv2.findContours(morphed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        min_area = (iw * ih) * 0.03  # At least 3% of image area
        max_area = (iw * ih) * 0.75

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area or area > max_area:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            aspect = float(h) / float(max(1, w))

            # Human face bounding box aspect ratio is typically between 0.85 and 2.2
            if 0.85 <= aspect <= 2.2:
                # Prefer contours closest to upper-center framing oval
                cnt_cx = x + w / 2.0
                cnt_cy = y + h / 2.0
                dist_center = np.sqrt(((cnt_cx - cx) / iw) ** 2 + ((cnt_cy - cy) / ih) ** 2)
                score = area - (dist_center * area * 0.6)
                candidates.append((score, [x, y, w, h]))

        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            fx, fy, fw, fh = candidates[0][1]

            # Add 12% margin around detected face boundary
            pad_w = int(fw * 0.12)
            pad_h = int(fh * 0.12)
            x1 = max(0, fx - pad_w)
            y1 = max(0, fy - pad_h)
            x2 = min(iw, fx + fw + pad_w)
            y2 = min(ih, fy + fh + pad_h)
            best_box = [x1, y1, x2 - x1, y2 - y1]

    except Exception as e:
        # Fallback to anthropometric framing box if segmentation fails
        pass

    bx, by, bw, bh = best_box
    face_raw = image_bgr[by:by + bh, bx:bx + bw]
    if face_raw.size == 0:
        return None, None

    # Standardize to 112x112 normalized face crop
    face_112 = cv2.resize(face_raw, (FACE_SIZE, FACE_SIZE), interpolation=cv2.INTER_AREA)
    return face_112, best_box


def detect_face_region(image_bgr: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[List[int]]]:
    """
    Canonical face localization entrypoint.
    Uses custom_localize_face() exclusively, adhering strictly to the No-Pretrained rule.
    """
    return custom_localize_face(image_bgr)


def preprocess_face_for_model(face_bgr: np.ndarray) -> np.ndarray:
    """
    Prepares a standardized 112x112 face crop for ForestFaceNet inference.

    Steps:
      1. Ensure 112x112 resolution.
      2. Convert BGR -> RGB.
      3. Histogram equalization on Y channel (illumination/lighting robustness).
      4. Normalize float values to [-1, 1] range (mean=0.5, std=0.5).
      5. Transpose to CHW shape (3, 112, 112).

    Returns:
        float32 numpy array with shape (3, 112, 112).
    """
    if face_bgr.shape[0] != FACE_SIZE or face_bgr.shape[1] != FACE_SIZE:
        face_bgr = cv2.resize(face_bgr, (FACE_SIZE, FACE_SIZE), interpolation=cv2.INTER_AREA)

    face_rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)

    # Lighting equalization on luminance channel
    face_yuv = cv2.cvtColor(face_rgb, cv2.COLOR_RGB2YUV)
    face_yuv[:, :, 0] = cv2.equalizeHist(face_yuv[:, :, 0])
    face_rgb = cv2.cvtColor(face_yuv, cv2.COLOR_YUV2RGB)

    face_float = face_rgb.astype(np.float32) / 255.0
    face_normalized = (face_float - np.array(MEAN)) / np.array(STD)
    face_chw = np.transpose(face_normalized, (2, 0, 1))
    return face_chw.astype(np.float32)


def pil_to_face_tensor(pil_image: Image.Image) -> Tuple[Optional[np.ndarray], Optional[List[int]]]:
    """Converts a PIL image to a preprocessed face tensor via custom face localization."""
    img_bgr = cv2.cvtColor(np.array(pil_image.convert("RGB")), cv2.COLOR_RGB2BGR)
    face_crop, bbox = custom_localize_face(img_bgr)
    if face_crop is None:
        return None, None
    face_tensor = preprocess_face_for_model(face_crop)
    return face_tensor, bbox


def augment_face(face_bgr: np.ndarray) -> List[np.ndarray]:
    """Generates natural augmented variants for ForestFaceNet training."""
    variants = [face_bgr]
    variants.append(cv2.flip(face_bgr, 1))

    for alpha in [0.85, 1.15]:
        variants.append(cv2.convertScaleAbs(face_bgr, alpha=alpha, beta=0))

    variants.append(cv2.GaussianBlur(face_bgr, (3, 3), 0))
    return [preprocess_face_for_model(v) for v in variants]
