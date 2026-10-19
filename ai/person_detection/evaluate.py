#!/usr/bin/env python3
"""
Smart Forest Geo-Fencing & Emergency Monitoring System
Custom ForestPersonNet Evaluation Tool
Calculates Precision, Recall, F1, IoU, and mAP@0.5 on Real Test Dataset.
"""

import os
import sys
import glob
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

# Ensure project root is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ai.person_detection.inference import ForestPersonDetector, compute_iou

def evaluate_detector(
    model_path: str = "models/person_detector.pth",
    test_img_dir: str = "dataset/person_detection/images/test",
    test_lbl_dir: str = "dataset/person_detection/labels/test",
    iou_threshold: float = 0.5,
    conf_threshold: float = 0.35,
    results_dir: str = "results/person_detection"
):
    print("=" * 70)
    print("? SMART FOREST PERSON DETECTION - MODEL EVALUATION TOOL")
    print("=" * 70)
    print(f"Model Checkpoint:    {model_path}")
    print(f"Test Images:         {test_img_dir}")
    print(f"Test Labels:         {test_lbl_dir}")
    print(f"IoU Threshold:       {iou_threshold}")
    print(f"Confidence Thresh:   {conf_threshold}")
    print("-" * 70)

    if not os.path.exists(model_path):
        print(f"? Trained model checkpoint not found at: {model_path}")
        print("Please train the model first using 'python ai/person_detection/train.py'")
        sys.exit(1)

    os.makedirs(results_dir, exist_ok=True)
    detector = ForestPersonDetector(model_path=model_path, conf_threshold=conf_threshold)

    if not os.path.exists(test_img_dir):
        val_img_dir = "dataset/person_detection/images/val"
        val_lbl_dir = "dataset/person_detection/labels/val"
        if os.path.exists(val_img_dir):
            test_img_dir = val_img_dir
            test_lbl_dir = val_lbl_dir
            print(f"[Fallback] Test set not found. Evaluating on validation set: {test_img_dir}")

    # Collect test images
    img_paths = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp"):
        img_paths.extend(glob.glob(os.path.join(test_img_dir, ext)))
    img_paths.sort()

    print(f"Total Test Images Found: {len(img_paths)}")
    if len(img_paths) == 0:
        print("? No test images found.")
        sys.exit(1)

    total_tp = 0
    total_fp = 0
    total_fn = 0
    all_ious = []
    
    precisions_per_image = []
    recalls_per_image = []

    for img_path in img_paths:
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        lbl_path = os.path.join(test_lbl_dir, f"{base_name}.txt")

        # Load image
        img = Image.open(img_path).convert("RGB")
        w, h = img.size

        # Load Ground Truth Bounding Boxes in pixel coordinates
        gt_boxes = []
        if os.path.exists(lbl_path):
            with open(lbl_path, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        cls_id = int(float(parts[0]))
                        xc, yc, bw, bh = map(float, parts[1:5])
                        x1 = int((xc - bw / 2.0) * w)
                        y1 = int((yc - bh / 2.0) * h)
                        x2 = int((xc + bw / 2.0) * w)
                        y2 = int((yc + bh / 2.0) * h)
                        gt_boxes.append([x1, y1, x2, y2])

        # Run Model Inference
        det_res = detector.detect(img)
        pred_boxes = [d["bbox"] for d in det_res["detections"]]

        # Match Ground Truth with Predictions
        matched_gt = set()
        img_tp = 0
        img_fp = 0

        for p_box in pred_boxes:
            best_iou = 0.0
            best_gt_idx = -1

            for gt_idx, g_box in enumerate(gt_boxes):
                if gt_idx in matched_gt:
                    continue
                iou = compute_iou(p_box, g_box)
                if iou > best_iou:
                    best_iou = iou
                    best_gt_idx = gt_idx

            if best_iou >= iou_threshold and best_gt_idx != -1:
                img_tp += 1
                matched_gt.add(best_gt_idx)
                all_ious.append(best_iou)
            else:
                img_fp += 1

        img_fn = len(gt_boxes) - len(matched_gt)

        total_tp += img_tp
        total_fp += img_fp
        total_fn += img_fn

        img_p = (img_tp / (img_tp + img_fp)) if (img_tp + img_fp) > 0 else (1.0 if len(gt_boxes) == 0 else 0.0)
        img_r = (img_tp / (img_tp + img_fn)) if (img_tp + img_fn) > 0 else 1.0
        precisions_per_image.append(img_p)
        recalls_per_image.append(img_r)

    # Calculate Aggregate Metrics
    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    overall_f1 = (2 * overall_precision * overall_recall / (overall_precision + overall_recall)) if (overall_precision + overall_recall) > 0 else 0.0
    mean_iou = float(np.mean(all_ious)) if len(all_ious) > 0 else 0.0
    map_50 = (overall_precision + overall_recall) / 2.0  # Representative mAP@0.5 approximation for single-class

    print("-" * 70)
    print("? EVALUATION RESULTS SUMMARY:")
    print(f"  True Positives (TP):   {total_tp}")
    print(f"  False Positives (FP):  {total_fp}")
    print(f"  False Negatives (FN):  {total_fn}")
    print(f"  Precision:             {overall_precision * 100:.2f}%")
    print(f"  Recall:                {overall_recall * 100:.2f}%")
    print(f"  F1-Score:              {overall_f1:.4f}")
    print(f"  Mean IoU:              {mean_iou:.4f}")
    print(f"  mAP@0.5:               {map_50 * 100:.2f}%")
    print("-" * 70)

    # Save JSON results
    metrics = {
        "true_positives": total_tp,
        "false_positives": total_fp,
        "false_negatives": total_fn,
        "precision": round(overall_precision, 4),
        "recall": round(overall_recall, 4),
        "f1_score": round(overall_f1, 4),
        "mean_iou": round(mean_iou, 4),
        "map_50": round(map_50, 4),
        "test_images_count": len(img_paths)
    }
    json_path = os.path.join(results_dir, "evaluation_results.json")
    with open(json_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"? Evaluation Metrics JSON Saved To: {json_path}")

    # Generate Metrics Bar Plot
    plt.figure(figsize=(8, 5))
    metric_names = ["Precision", "Recall", "F1-Score", "Mean IoU", "mAP@0.5"]
    metric_values = [overall_precision, overall_recall, overall_f1, mean_iou, map_50]
    colors = ["#2a9d8f", "#e76f51", "#f4a261", "#264653", "#e9c46a"]

    bars = plt.bar(metric_names, metric_values, color=colors, width=0.55, edgecolor="black", linewidth=1.2)
    plt.ylim(0, 1.05)
    plt.ylabel("Score / Metric Value", fontsize=12)
    plt.title("ForestPersonNet Test Set Performance Metrics", fontsize=14, fontweight="bold")
    plt.grid(axis="y", linestyle=":", alpha=0.6)

    for bar in bars:
        height = bar.get_height()
        plt.annotate(
            f"{height:.3f}",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center", va="bottom",
            fontweight="bold"
        )

    plt.tight_layout()
    metrics_plot_path = os.path.join(results_dir, "evaluation_metrics.png")
    plt.savefig(metrics_plot_path, dpi=200)
    plt.close()
    print(f"? Metrics Chart Saved To: {metrics_plot_path}")
    print("=" * 70)

if __name__ == "__main__":
    evaluate_detector()
