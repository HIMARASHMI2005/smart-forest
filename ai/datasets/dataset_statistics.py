#!/usr/bin/env python3
"""
Smart Forest Geo-Fencing System - Dataset Statistics & Profiling
Analyzes bounding box dimensions, aspect ratios, person counts, and scene density.
"""

import os
import sys
import glob
from collections import Counter
import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
PERSON_DATASET = os.path.join(project_root, "dataset", "person_detection")

def compute_dataset_statistics():
    print("=" * 70)
    print("[STATS] REAL DATASET STATISTICAL DISTRIBUTION & PROFILING")
    print("=" * 70)

    person_counts_counter = Counter()
    widths = []
    heights = []
    areas = []
    aspect_ratios = []

    splits = ["train", "val", "test"]
    for split in splits:
        lbl_dir = os.path.join(PERSON_DATASET, "labels", split)
        lbl_files = glob.glob(os.path.join(lbl_dir, "*.txt"))

        for lf in lbl_files:
            with open(lf, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]

            person_counts_counter[len(lines)] += 1
            for l in lines:
                parts = l.split()
                if len(parts) == 5:
                    w = float(parts[3])
                    h = float(parts[4])
                    widths.append(w)
                    heights.append(h)
                    areas.append(w * h)
                    aspect_ratios.append(h / w if w > 0 else 0)

    print("\n[PERSON COUNT PER IMAGE DISTRIBUTION]")
    for p_cnt in sorted(person_counts_counter.keys()):
        num_imgs = person_counts_counter[p_cnt]
        label = "Single Person" if p_cnt == 1 else (f"Group of {p_cnt}" if p_cnt > 1 else "Zero Person")
        print(f"  * {p_cnt} Person(s) ({label:16s}): {num_imgs} images")

    if widths:
        print("\n[BOUNDING BOX METRICS (NORMALIZED [0, 1])]")
        print(f"  * Mean Bounding Box Width:       {np.mean(widths):.4f} (std: {np.std(widths):.4f})")
        print(f"  * Mean Bounding Box Height:      {np.mean(heights):.4f} (std: {np.std(heights):.4f})")
        print(f"  * Mean Bounding Box Area:        {np.mean(areas):.4f}")
        print(f"  * Mean Aspect Ratio (H / W):     {np.mean(aspect_ratios):.2f}")
    print("=" * 70)

if __name__ == "__main__":
    compute_dataset_statistics()
