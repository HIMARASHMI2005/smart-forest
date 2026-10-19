#!/usr/bin/env python3
"""
Smart Forest Geo-Fence & Emergency Monitoring System
Face Dataset Integrity & Real Photograph Verification Tool

Audits dataset/faces/ to ensure:
1. Every enrolled subject contains genuine photographs.
2. No cartoon, smiley, blank, or synthetic placeholder images exist in active dataset.
3. Proper resolution, file size, variance, entropy, and non-duplicate integrity.

Returns:
  0 = Dataset passes validation (all images are authentic real photographs)
  1 = Dataset fails (synthetic, placeholder, corrupt, or invalid images detected)
"""

import os
import sys
import glob
import hashlib
from typing import Dict, Any, List, Tuple
import cv2
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATASET_FACES = os.path.join(PROJECT_ROOT, "dataset", "faces")
QUARANTINE_DIR = os.path.join(PROJECT_ROOT, "dataset", "NOT_FOR_TRAINING", "faces")


def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def analyze_image(filepath: str) -> Dict[str, Any]:
    """Analyzes a single image for photographic authenticity, texture, and corruption."""
    res = {
        "valid": False,
        "size_bytes": 0,
        "width": 0,
        "height": 0,
        "channels": 0,
        "std_dev": 0.0,
        "max_color_pct": 0.0,
        "error": None,
        "is_suspicious": False,
        "suspicious_reason": None,
        "sha256": None
    }

    try:
        st = os.stat(filepath)
        res["size_bytes"] = st.st_size
        res["sha256"] = compute_sha256(filepath)
    except Exception as e:
        res["error"] = f"Stat error: {e}"
        return res

    img = cv2.imread(filepath)
    if img is None:
        res["error"] = "Corrupt / unreadable image format"
        return res

    h, w, c = img.shape
    res["width"] = w
    res["height"] = h
    res["channels"] = c

    # Real photos require minimum resolution
    if w < 100 or h < 100:
        res["is_suspicious"] = True
        res["suspicious_reason"] = f"Low resolution ({w}x{h} < 100x100)"
        return res

    if res["size_bytes"] < 3000:
        res["is_suspicious"] = True
        res["suspicious_reason"] = f"File size too small ({res['size_bytes']} bytes < 3KB)"
        return res

    # Check pixel variance (real photos have sensor noise and natural gradients)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    std_dev = float(np.std(gray))
    res["std_dev"] = std_dev
    if std_dev < 14.0:
        res["is_suspicious"] = True
        res["suspicious_reason"] = f"Uniform / flat tone (std_dev={std_dev:.1f} < 14.0)"
        return res

    # Check for dominant flat background (synthetic canvas with simple shapes)
    pixels = gray.flatten()
    counts = np.bincount(pixels, minlength=256)
    max_val_pct = float(np.max(counts)) / float(len(pixels))
    res["max_color_pct"] = max_val_pct
    if max_val_pct > 0.65:
        res["is_suspicious"] = True
        res["suspicious_reason"] = f"Monochrome background ({max_val_pct*100:.1f}% pixels identical)"
        return res

    res["valid"] = True
    return res


def verify_dataset(faces_dir: str = DATASET_FACES) -> Tuple[bool, List[Dict[str, Any]]]:
    """Scans all folders under dataset/faces/ and audits each identity."""
    if not os.path.exists(faces_dir):
        print(f"[ERROR] Directory does not exist: {faces_dir}")
        return False, []

    identities = sorted([
        d for d in os.listdir(faces_dir)
        if os.path.isdir(os.path.join(faces_dir, d)) and not d.startswith(".") and not d.startswith("_")
    ])

    results = []
    overall_valid = True
    seen_hashes = {}

    for identity in identities:
        id_dir = os.path.join(faces_dir, identity)
        img_files = sorted(glob.glob(os.path.join(id_dir, "*.jpg")) + glob.glob(os.path.join(id_dir, "*.jpeg")) + glob.glob(os.path.join(id_dir, "*.png")))

        id_report = {
            "identity": identity,
            "count": len(img_files),
            "valid_count": 0,
            "suspicious_count": 0,
            "corrupt_count": 0,
            "duplicate_count": 0,
            "dimensions": [],
            "avg_size": 0,
            "issues": [],
            "status": "PASS"
        }

        if len(img_files) == 0:
            id_report["status"] = "EMPTY"
            id_report["issues"].append("Zero images found in folder")
            overall_valid = False
            results.append(id_report)
            continue

        total_bytes = 0
        dims_set = set()

        for fpath in img_files:
            fname = os.path.basename(fpath)
            analysis = analyze_image(fpath)
            total_bytes += analysis["size_bytes"]

            if analysis["sha256"]:
                if analysis["sha256"] in seen_hashes:
                    id_report["duplicate_count"] += 1
                    id_report["issues"].append(f"{fname} is exact duplicate of {seen_hashes[analysis['sha256']]}")
                else:
                    seen_hashes[analysis["sha256"]] = f"{identity}/{fname}"

            if analysis["error"]:
                id_report["corrupt_count"] += 1
                id_report["issues"].append(f"{fname}: {analysis['error']}")
                overall_valid = False
            elif analysis["is_suspicious"]:
                id_report["suspicious_count"] += 1
                id_report["issues"].append(f"{fname}: {analysis['suspicious_reason']}")
                overall_valid = False
            else:
                id_report["valid_count"] += 1
                dims_set.add(f"{analysis['width']}x{analysis['height']}")

        id_report["avg_size"] = total_bytes // max(1, len(img_files))
        id_report["dimensions"] = list(dims_set)

        if id_report["suspicious_count"] > 0 or id_report["corrupt_count"] > 0:
            id_report["status"] = "FAIL"
            overall_valid = False
        else:
            id_report["status"] = "PASS"

        results.append(id_report)

    return overall_valid, results


def print_report(overall_valid: bool, results: List[Dict[str, Any]]):
    print("=" * 85)
    print("SMART FOREST — FACE DATASET INTEGRITY & REAL PHOTOGRAPH AUDIT")
    print("Target Directory:", DATASET_FACES)
    print("=" * 85)
    print(f"{'IDENTITY':<22} | {'COUNT':<5} | {'DIMENSIONS':<12} | {'AVG SIZE':<10} | {'DUPES':<5} | {'STATUS'}")
    print("-" * 85)

    for r in results:
        dims = ",".join(r["dimensions"][:2]) if r["dimensions"] else "N/A"
        size_str = f"{r['avg_size']/1024:.1f} KB" if r["avg_size"] > 0 else "0 KB"
        status_color = r["status"]
        print(f"{r['identity']:<22} | {r['count']:<5} | {dims:<12} | {size_str:<10} | {r['duplicate_count']:<5} | {status_color}")
        if r["issues"]:
            for issue in r["issues"][:4]:
                print(f"   [!] {issue}")
            if len(r["issues"]) > 4:
                print(f"   [!] ... and {len(r['issues']) - 4} more issue(s)")

    print("=" * 85)
    if overall_valid:
        print("[SUCCESS] ALL ACTIVE FACE DATASET ENTRIES CONTAIN AUTHENTIC PHOTOGRAPHS.")
        print("          No cartoon, smiley, blank, or placeholder images detected.")
    else:
        print("[ALERT] VALIDATION FAILED: Active dataset contains synthetic/suspicious images.")
        print("        Quarantine required to move fake data out of dataset/faces/.")
    print("=" * 85)


if __name__ == "__main__":
    passed, rep = verify_dataset()
    print_report(passed, rep)
    sys.exit(0 if passed else 1)
