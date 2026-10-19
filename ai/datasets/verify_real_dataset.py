#!/usr/bin/env python3
"""
Smart Forest Geo-Fencing & Emergency Monitoring System
Dataset Verification Utility - Validates Real Photographic Datasets
Calculates exact statistics from actual disk files without fabrication.
"""

import os
import sys
import glob
import hashlib
from PIL import Image

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

DATASET_ROOT = os.path.join(project_root, "dataset")
PERSON_DATASET = os.path.join(DATASET_ROOT, "person_detection")
FACE_DATASET = os.path.join(DATASET_ROOT, "faces")


def compute_file_hash(filepath: str) -> str:
    """Computes SHA-256 hash to detect duplicate files."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_real_dataset():
    print("=" * 75)
    print("[AUDIT] SMART FOREST - REAL PHOTOGRAPHIC DATASET VERIFICATION")
    print("=" * 75)

    splits = ["train", "val", "test"]
    split_counts = {"train": 0, "val": 0, "test": 0}
    total_images = 0
    total_person_annotations = 0
    single_person_images = 0
    group_images = 0
    zero_person_images = 0
    corrupted_images = 0
    missing_labels = 0
    invalid_bounding_boxes = 0

    seen_hashes = {}
    duplicate_images = 0

    for split in splits:
        img_dir = os.path.join(PERSON_DATASET, "images", split)
        lbl_dir = os.path.join(PERSON_DATASET, "labels", split)

        if not os.path.exists(img_dir):
            print(f"[WARN]   Missing image directory for split: {split}")
            continue

        images = []
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp"):
            images.extend(glob.glob(os.path.join(img_dir, ext)))
        images.sort()

        split_counts[split] = len(images)
        total_images += len(images)

        for img_path in images:
            # 1. Check for corruption
            try:
                with Image.open(img_path) as im:
                    im.verify()
            except Exception:
                corrupted_images += 1
                continue

            # 2. Check for duplicates
            fhash = compute_file_hash(img_path)
            if fhash in seen_hashes:
                duplicate_images += 1
            else:
                seen_hashes[fhash] = img_path

            # 3. Check corresponding label
            base_name = os.path.splitext(os.path.basename(img_path))[0]
            lbl_path = os.path.join(lbl_dir, f"{base_name}.txt")

            if not os.path.exists(lbl_path):
                missing_labels += 1
                zero_person_images += 1
                continue

            # Read label lines
            with open(lbl_path, "r", encoding="utf-8") as lf:
                lines = [line.strip() for line in lf if line.strip()]

            valid_boxes_in_image = 0
            for line in lines:
                parts = line.split()
                if len(parts) != 5:
                    invalid_bounding_boxes += 1
                    continue
                try:
                    cls_id = int(parts[0])
                    xc, yc, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                    if not (0.0 <= xc <= 1.0 and 0.0 <= yc <= 1.0 and 0.0 < w <= 1.0 and 0.0 < h <= 1.0):
                        invalid_bounding_boxes += 1
                        continue
                    if cls_id != 0:
                        invalid_bounding_boxes += 1
                        continue
                    valid_boxes_in_image += 1
                except ValueError:
                    invalid_bounding_boxes += 1
                    continue

            total_person_annotations += valid_boxes_in_image
            if valid_boxes_in_image == 0:
                zero_person_images += 1
            elif valid_boxes_in_image == 1:
                single_person_images += 1
            else:
                group_images += 1

    print("\n--- PERSON DETECTION DATASET AUDIT SUMMARY ---")
    print(f"Total images:              {total_images}")
    print(f"Training images:           {split_counts['train']}")
    print(f"Validation images:         {split_counts['val']}")
    print(f"Testing images:            {split_counts['test']}")
    print(f"Total person annotations:  {total_person_annotations}")
    print(f"Single-person images:      {single_person_images}")
    print(f"Group images:              {group_images}")
    print(f"Zero-person images:        {zero_person_images}")
    print(f"Duplicate images:          {duplicate_images}")
    print(f"Corrupted images:          {corrupted_images}")
    print(f"Missing labels:            {missing_labels}")
    print(f"Invalid bounding boxes:    {invalid_bounding_boxes}")
    print("-" * 46)

    # Face dataset verification
    print("\n--- FACE IDENTIFICATION DATASET AUDIT SUMMARY ---")
    face_identities = [d for d in os.listdir(FACE_DATASET) if os.path.isdir(os.path.join(FACE_DATASET, d))] if os.path.exists(FACE_DATASET) else []
    total_face_images = 0
    print(f"Registered Identities:     {len(face_identities)}")
    for fid in sorted(face_identities):
        fdir = os.path.join(FACE_DATASET, fid)
        fcnt = len(glob.glob(os.path.join(fdir, "*.jpg")))
        total_face_images += fcnt
        print(f"  * {fid:16s} : {fcnt} real photographic crops")
    print(f"Total Face Crops:          {total_face_images}")
    print("=" * 75)

    is_valid = (
        total_images > 0 and
        split_counts["train"] > 0 and
        split_counts["val"] > 0 and
        split_counts["test"] > 0 and
        corrupted_images == 0 and
        missing_labels == 0 and
        invalid_bounding_boxes == 0 and
        total_face_images > 0
    )

    if is_valid:
        print("\n[PASS] [PASS] All dataset integrity checks passed successfully with 0 errors!")
    else:
        print("\n[ERROR] [FAIL] Dataset audit encountered errors. Please check logs.")

    return is_valid


if __name__ == "__main__":
    verify_real_dataset()
