#!/usr/bin/env python3
"""
Smart Forest Geo-Fencing System - Dataset Split Utility
Verifies or re-balances train/val/test splits cleanly.
"""

import os
import sys
import glob

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
PERSON_DATASET = os.path.join(project_root, "dataset", "person_detection")

def verify_splits():
    splits = ["train", "val", "test"]
    print("Checking split distribution in person_detection dataset...")
    total = 0
    for s in splits:
        img_dir = os.path.join(PERSON_DATASET, "images", s)
        cnt = len(glob.glob(os.path.join(img_dir, "*.jpg")))
        total += cnt
        print(f"  * {s:6s}: {cnt} images")
    print(f"Total across all splits: {total} images")
    return total > 0

if __name__ == "__main__":
    verify_splits()
