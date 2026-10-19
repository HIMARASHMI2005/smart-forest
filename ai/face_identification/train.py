#!/usr/bin/env python3
"""
Smart Forest Geo-Fencing & Emergency Monitoring System
ForestFaceNet Training Pipeline - From Random Initialization Only.
No pretrained FaceNet, ArcFace, or any external weights are used.
"""

import os
import sys
import argparse
import json
import time
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split
from torch.optim import AdamW
from torch.optim.lr_scheduler import StepLR
from sklearn.metrics import confusion_matrix, classification_report
import seaborn as sns

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ai.face_identification.model import ForestFaceNet
from ai.face_identification.dataset import FaceDataset


def train_face_model(
    epochs: int = 30,
    batch_size: int = 16,
    learning_rate: float = 5e-4,
    data_dir: str = "dataset/faces",
    save_path: str = "models/face_identifier.pth",
    results_dir: str = "results/face_identification",
    val_split: float = 0.15
):
    print("=" * 70)
    print("SMART FOREST FACE IDENTIFICATION - MODEL TRAINING PIPELINE")
    print("   [NO PRETRAINED WEIGHTS - KAIMING RANDOM INITIALIZATION ONLY]")
    print("=" * 70)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)

    # 1. Load Dataset
    print(f"\nLoading face dataset from: {data_dir}")
    try:
        full_dataset = FaceDataset(root_dir=data_dir, is_train=True, augment=True)
    except (FileNotFoundError, ValueError) as e:
        print(f"[ERROR] Dataset Error: {e}")
        print("Please ensure face images are stored in dataset/faces/person_XXX/ directories.")
        sys.exit(1)

    num_classes = full_dataset.num_classes()
    print(f"Identities:    {num_classes}")
    print(f"Total Samples: {len(full_dataset)}")

    if num_classes < 2:
        print("[ERROR] At least 2 registered identities are required for training.")
        sys.exit(1)

    # Train / Val split
    val_size = max(1, int(len(full_dataset) * val_split))
    train_size = len(full_dataset) - val_size
    train_ds, val_ds = random_split(full_dataset, [train_size, val_size])
    print(f"Train Samples: {train_size} | Val Samples: {val_size}\n")

    train_loader = DataLoader(train_ds, batch_size=min(batch_size, train_size), shuffle=True, drop_last=False)
    val_loader = DataLoader(val_ds, batch_size=min(batch_size, val_size), shuffle=False)

    # 2. Build Model (Random Initialization)
    model = ForestFaceNet(embedding_dim=128, num_classes=num_classes).to(device)
    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"ForestFaceNet Parameters: {total_params:,} (Randomly Initialized - No Pretrained Weights)")

    # 3. Loss + Optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    scheduler = StepLR(optimizer, step_size=max(1, epochs // 3), gamma=0.5)

    # 4. Training Loop
    history = {"train_loss": [], "val_loss": [], "train_acc": [], "val_acc": []}
    best_val_acc = 0.0
    start_time = time.time()

    print("[START] Starting Training...\n")
    for epoch in range(1, epochs + 1):
        model.train()
        train_loss, train_correct, train_total = 0.0, 0, 0

        for faces, labels in train_loader:
            faces, labels = faces.to(device), labels.to(device)
            optimizer.zero_grad()
            embeddings, logits = model(faces)
            loss = criterion(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=3.0)
            optimizer.step()
            train_loss += loss.item() * faces.size(0)
            train_correct += (logits.argmax(dim=1) == labels).sum().item()
            train_total += faces.size(0)

        # Validation
        model.eval()
        val_loss, val_correct, val_total = 0.0, 0, 0
        with torch.no_grad():
            for faces, labels in val_loader:
                faces, labels = faces.to(device), labels.to(device)
                embeddings, logits = model(faces)
                loss = criterion(logits, labels)
                val_loss += loss.item() * faces.size(0)
                val_correct += (logits.argmax(dim=1) == labels).sum().item()
                val_total += faces.size(0)

        t_loss = train_loss / train_total
        v_loss = val_loss / val_total
        t_acc = train_correct / train_total * 100
        v_acc = val_correct / val_total * 100

        history["train_loss"].append(t_loss)
        history["val_loss"].append(v_loss)
        history["train_acc"].append(t_acc)
        history["val_acc"].append(v_acc)

        scheduler.step()
        print(f"Epoch [{epoch:03d}/{epochs:03d}] | Train Loss: {t_loss:.4f} | Train Acc: {t_acc:.2f}% | Val Loss: {v_loss:.4f} | Val Acc: {v_acc:.2f}%")

        if v_acc >= best_val_acc:
            best_val_acc = v_acc
            torch.save(model.state_dict(), save_path)  # canonical: models/face_identifier.pth

    print(f"\n[SUCCESS] Training Completed in {time.time() - start_time:.2f}s")
    print(f"[SAVED] Best Model Saved. Best Val Accuracy: {best_val_acc:.2f}%")

    # 5. Save class mapping
    class_map = {v: k for k, v in full_dataset.class_to_idx.items()}
    class_map_path = os.path.join(project_root, "models", "face_class_map.json")
    os.makedirs(os.path.dirname(class_map_path), exist_ok=True)
    with open(class_map_path, "w") as f:
        json.dump(class_map, f, indent=2)
    print(f"[LOG] Class Map Saved To: {class_map_path}")

    # 6. Loss Curve Plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].plot(history["train_loss"], label="Train Loss", color="#2a9d8f", lw=2)
    axes[0].plot(history["val_loss"], label="Val Loss", color="#e76f51", lw=2, linestyle="--")
    axes[0].set_title("Loss Curve", fontsize=13, fontweight="bold")
    axes[0].set_xlabel("Epoch"); axes[0].set_ylabel("Cross-Entropy Loss")
    axes[0].legend(); axes[0].grid(True, linestyle=":", alpha=0.5)

    axes[1].plot(history["train_acc"], label="Train Acc %", color="#2a9d8f", lw=2)
    axes[1].plot(history["val_acc"], label="Val Acc %", color="#e76f51", lw=2, linestyle="--")
    axes[1].set_title("Accuracy Curve", fontsize=13, fontweight="bold")
    axes[1].set_xlabel("Epoch"); axes[1].set_ylabel("Accuracy (%)")
    axes[1].legend(); axes[1].grid(True, linestyle=":", alpha=0.5)

    plt.tight_layout()
    plt.savefig(os.path.join(results_dir, "training_curves.png"), dpi=200)
    plt.close()

    # 7. Confusion Matrix on val set
    model.load_state_dict(torch.load(save_path, map_location=device))
    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for faces, labels in val_loader:
            faces = faces.to(device)
            _, logits = model(faces)
            preds = logits.argmax(dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labels.numpy())

    class_labels = full_dataset.class_names
    if len(np.unique(all_labels)) > 1:
        cm = confusion_matrix(all_labels, all_preds)
        plt.figure(figsize=(max(6, num_classes), max(5, num_classes)))
        sns.heatmap(cm, annot=True, fmt="d", cmap="YlOrRd",
                    xticklabels=class_labels, yticklabels=class_labels)
        plt.title("ForestFaceNet Confusion Matrix (Validation Set)", fontweight="bold")
        plt.ylabel("True Label"); plt.xlabel("Predicted Label")
        plt.tight_layout()
        plt.savefig(os.path.join(results_dir, "confusion_matrix.png"), dpi=200)
        plt.close()
        print("[PLOT] Confusion Matrix saved.")

    # 8. Save training history JSON
    with open(os.path.join(results_dir, "training_history.json"), "w") as f:
        json.dump({"best_val_acc": best_val_acc, "history": history}, f, indent=2)
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train ForestFaceNet from scratch.")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=5e-4)
    parser.add_argument("--data-dir", type=str, default="dataset/faces")
    parser.add_argument("--save-path", type=str, default="models/face_identifier.pth")
    args = parser.parse_args()

    train_face_model(
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        data_dir=args.data_dir,
        save_path=args.save_path
    )
