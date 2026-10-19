"""
Smart Forest Geo-Fence & Emergency Monitoring System
Face Photograph Authenticity & Quality Validator

Ensures captured images submitted during registration are genuine photographs:
- Enforces minimum resolution
- Checks image readability and corruption
- Rejects monochrome, flat-background, or placeholder images
- Detects synthetic smiley/cartoon faces
- Uses skin-chrominance and texture heuristics (without relying solely on them)
"""

import cv2
import numpy as np
from typing import Tuple


def validate_real_photograph(
    image_bgr: np.ndarray,
    min_width: int = 120,
    min_height: int = 120,
    is_pre_cropped: bool = False
) -> Tuple[bool, str]:
    """
    Validates that the provided image is a genuine human photograph rather than a
    blank frame, cartoon, smiley-face, or synthetic placeholder.

    Args:
        image_bgr: BGR numpy image array.
        min_width: Minimum allowable width in pixels.
        min_height: Minimum allowable height in pixels.
        is_pre_cropped: Whether the image is a tight face crop or a full webcam frame.

    Returns:
        (is_valid, message): Tuple of boolean and informative status message.
    """
    if image_bgr is None or not isinstance(image_bgr, np.ndarray):
        return False, "Photo capture failed: Invalid or empty image data received."

    if image_bgr.size == 0 or len(image_bgr.shape) < 2:
        return False, "Photo capture failed: Image contains no pixel data."

    h, w = image_bgr.shape[:2]

    # 1. Resolution Check
    effective_min_w = min_width if is_pre_cropped else max(min_width, 160)
    effective_min_h = min_height if is_pre_cropped else max(min_height, 120)

    if w < effective_min_w or h < effective_min_h:
        return False, f"Photo capture failed: Image resolution ({w}x{h}) is too low. Expected at least {effective_min_w}x{effective_min_h}."

    # Convert to grayscale for variance and texture analysis
    if len(image_bgr.shape) == 3 and image_bgr.shape[2] == 3:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_bgr

    # 2. Pixel Standard Deviation (Texture / Sensor Noise Check)
    # Synthetic flat canvases (e.g. np.ones(...) * 180 with smiley) have near-zero or very low std_dev
    std_dev = float(np.std(gray))
    if std_dev < 14.0:
        return False, "Photo capture failed: Image appears to be a synthetic placeholder or blank frame. Please capture a real photograph using your webcam."

    # 3. Dominant Color / Flat Background Ratio Check
    # A real human photograph has a complex distribution of tonal values.
    # If more than 65% of all pixels have identical or nearly identical intensity, it is a synthetic graphic.
    flat_pixels = gray.flatten()
    hist, _ = np.histogram(flat_pixels, bins=32, range=(0, 256))
    max_bin_ratio = float(np.max(hist)) / float(len(flat_pixels))

    if max_bin_ratio > 0.65:
        return False, "Photo capture failed: Flat background or placeholder detected. Please capture a real photograph with natural lighting."

    # 4. Color Channels Diversity Check
    if len(image_bgr.shape) == 3 and image_bgr.shape[2] == 3:
        b, g, r = cv2.split(image_bgr)
        # Check if image is completely grayscale or artificial monochrome
        rg_diff = float(np.mean(np.abs(r.astype(np.int32) - g.astype(np.int32))))
        gb_diff = float(np.mean(np.abs(g.astype(np.int32) - b.astype(np.int32))))
        
        # In real human skin and clothing, there is natural color variance across R, G, and B.
        # If all 3 channels are virtually identical (diff < 1.0) and std_dev is modest, it's synthetic grayscale.
        if rg_diff < 1.2 and gb_diff < 1.2 and std_dev < 25.0:
            return False, "Photo capture failed: Monochromatic or synthetic graphic detected. Please use a live color camera."

        # 5. Human Skin Chrominance Heuristic (Quality check, not absolute proof)
        # YCbCr space: Cr in [130, 175], Cb in [75, 130] captures natural human skin tones under diverse lighting
        ycbcr = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2YCrCb)
        cr = ycbcr[:, :, 1]
        cb = ycbcr[:, :, 2]
        skin_mask = (cr >= 128) & (cr <= 178) & (cb >= 75) & (cb <= 135)
        skin_pixel_pct = float(np.sum(skin_mask)) / float(w * h)

        # In a framed face portrait, skin tones should occupy at least 3% of the image area
        if skin_pixel_pct < 0.03:
            # Check HSV fallback (H in [0, 25] or [160, 180])
            hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
            h_channel = hsv[:, :, 0]
            s_channel = hsv[:, :, 1]
            v_channel = hsv[:, :, 2]
            hsv_skin = ((h_channel <= 25) | (h_channel >= 165)) & (s_channel >= 30) & (v_channel >= 40)
            hsv_pct = float(np.sum(hsv_skin)) / float(w * h)

            if hsv_pct < 0.03:
                return False, "Photo capture failed: No human subject detected in the camera frame. Please position your face clearly in the camera."

    return True, "Valid real photograph"
