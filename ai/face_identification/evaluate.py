#!/usr/bin/env python3
"""
Evaluate ForestFaceNet on real test face images.
Generates Accuracy, Precision, Recall, F1, Confusion Matrix.
"""
import os, sys, json
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
from torch.utils.data import DataLoader, random_split
from sklearn.metrics import (classification_report, confusion_matrix,
                              precision_score, recall_score, f1_score)
import seaborn as sns

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ai.face_identification.model import ForestFaceNet
from ai.face_identification.dataset import FaceDataset


def evaluate_face_model(
    model_path: str = "models/face_identifier.pth",
    data_dir: str = "dataset/faces",
    results_dir: str = "results/face_identification"
):
    print("=" * 70)
    print("? SMART FOREST FACE IDENTIFICATION - MODEL EVALUATION")
    print("=" * 70)

    os.makedirs(results_dir, exist_ok=True)

    if not os.path.exists(model_path):
        print(f"? Trained model not found: {model_path}")
        sys.exit(1)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Load dataset (no augmentation for evaluation)
    try:
        dataset = FaceDataset(root_dir=data_dir, is_train=False, augment=False)
    except (FileNotFoundError, ValueError) as e:
        print(f"? Dataset error: {e}"); sys.exit(1)

    num_classes = dataset.num_classes()
    class_names = dataset.class_names

    # Use entire dataset as test set for evaluation
    loader = DataLoader(dataset, batch_size=16, shuffle=False)

    model = ForestFaceNet(embedding_dim=128, num_classes=num_classes)
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.to(device).eval()

    all_preds, all_labels = [], []
    with torch.no_grad():
        for faces, labels in loader:
            faces = faces.to(device)
            _, logits = model(faces)
            preds = logits.argmax(dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labels.numpy())

    all_preds = np.array(all_preds)
    all_labels = np.array(all_labels)

    accuracy = (all_preds == all_labels).mean() * 100
    avg = "macro" if num_classes > 2 else "binary"
    precision = precision_score(all_labels, all_preds, average=avg, zero_division=0)
    recall    = recall_score(all_labels, all_preds, average=avg, zero_division=0)
    f1        = f1_score(all_labels, all_preds, average=avg, zero_division=0)

    print(f"\nTest Samples:   {len(all_labels)}")
    print(f"Accuracy:       {accuracy:.2f}%")
    print(f"Precision:      {precision*100:.2f}%")
    print(f"Recall:         {recall*100:.2f}%")
    print(f"F1-Score:       {f1:.4f}\n")
    print(classification_report(all_labels, all_preds, target_names=class_names, zero_division=0))

    # Confusion Matrix
    cm = confusion_matrix(all_labels, all_preds)
    plt.figure(figsize=(max(6, num_classes), max(5, num_classes - 1)))
    sns.heatmap(cm, annot=True, fmt="d", cmap="YlOrRd",
                xticklabels=class_names, yticklabels=class_names)
    plt.title("ForestFaceNet Evaluation Confusion Matrix", fontweight="bold")
    plt.ylabel("True"); plt.xlabel("Predicted")
    plt.tight_layout()
    cm_path = os.path.join(results_dir, "confusion_matrix.png")
    plt.savefig(cm_path, dpi=200); plt.close()
    print(f"? Confusion Matrix ? {cm_path}")

    results = {
        "accuracy_pct": round(accuracy, 2),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1_score": round(float(f1), 4),
        "test_samples": len(all_labels),
        "num_classes": num_classes
    }
    with open(os.path.join(results_dir, "evaluation_results.json"), "w") as f:
        json.dump(results, f, indent=2)
    print(f"? Results ? {os.path.join(results_dir, 'evaluation_results.json')}")
    print("=" * 70)


if __name__ == "__main__":
    evaluate_face_model()
