#!/usr/bin/env python3
"""
Smart Forest Geo-Fencing System - Bounding Box Annotation Validator
Verifies YOLO coordinate bounds, non-empty annotations, and label-image pairings.
"""

import os
import sys
import glob

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
PERSON_DATASET = os.path.join(project_root, "dataset", "person_detection")

def validate_all_annotations():
    print("Checking label and bounding box validity across splits...")
    splits = ["train", "val", "test"]
    total_valid = 0
    total_invalid = 0

    for split in splits:
        lbl_dir = os.path.join(PERSON_DATASET, "labels", split)
        img_dir = os.path.join(PERSON_DATASET, "images", split)
        lbl_files = glob.glob(os.path.join(lbl_dir, "*.txt"))

        for lf in lbl_files:
            base = os.path.splitext(os.path.basename(lf))[0]
            # Check image exists
            img_path = os.path.join(img_dir, f"{base}.jpg")
            if not os.path.exists(img_path):
                print(f"[ERROR] Missing image for label: {lf}")
                total_invalid += 1
                continue

            with open(lf, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]

            if len(lines) == 0:
                print(f"[WARN]  Empty label file: {lf}")
                total_invalid += 1
                continue

            for l in lines:
                parts = l.split()
                if len(parts) != 5:
                    print(f"[ERROR] Malformed line in {lf}: {l}")
                    total_invalid += 1
                    continue
                try:
                    c, xc, yc, w, h = int(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                    if not (0.0 <= xc <= 1.0 and 0.0 <= yc <= 1.0 and 0.0 < w <= 1.0 and 0.0 < h <= 1.0):
                        print(f"[ERROR] Out-of-bound box in {lf}: {l}")
                        total_invalid += 1
                    else:
                        total_valid += 1
                except ValueError:
                    print(f"[ERROR] Non-numeric values in {lf}: {l}")
                    total_invalid += 1

    print(f"Annotation validation complete: {total_valid} valid boxes, {total_invalid} invalid.")
    return total_invalid == 0

if __name__ == "__main__":
    validate_all_annotations()
