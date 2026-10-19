#!/usr/bin/env python3
"""
Smart Forest Geo-Fencing & Emergency Monitoring System
Custom ForestPersonNet Training Pipeline (From Scratch - Random Weights Only)
"""

import os
import sys
import argparse
import time
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
from torch.utils.data import DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

# Ensure project root is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ai.person_detection.model import ForestPersonNet
from ai.person_detection.loss import CustomDetectionLoss
from ai.person_detection.dataset import ForestPersonDataset

def train_model(
    epochs: int = 25,
    batch_size: int = 8,
    learning_rate: float = 1e-3,
    img_size: int = 224,
    data_dir: str = "dataset/person_detection",
    save_path: str = "models/person_detector.pth",
    results_dir: str = "results/person_detection"
):
    print("=" * 70)
    print("SMART FOREST PERSON DETECTION - MODEL TRAINING PIPELINE")
    print("   [STRICT RULE: NO PRETRAINED WEIGHTS / RANDOM INITIALIZATION ONLY]")
    print("=" * 70)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Compute Device:      {device}")
    print(f"Target Epochs:       {epochs}")
    print(f"Batch Size:          {batch_size}")
    print(f"Learning Rate:       {learning_rate}")
    print(f"Input Resolution:    {img_size}x{img_size}")
    print(f"Dataset Root:        {data_dir}")
    print(f"Save Path:           {save_path}")
    print("-" * 70)

    # 1. Prepare Directories
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    os.makedirs(os.path.join(project_root, "ai", "models"), exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)

    train_img_dir = os.path.join(data_dir, "images", "train")
    train_lbl_dir = os.path.join(data_dir, "labels", "train")
    val_img_dir = os.path.join(data_dir, "images", "val")
    val_lbl_dir = os.path.join(data_dir, "labels", "val")

    if not os.path.exists(train_img_dir):
        print(f"[ERROR] Training directory not found: {train_img_dir}")
        print("Please run the dataset preparation/verification script first.")
        sys.exit(1)

    # 2. Build Datasets & Dataloaders
    train_dataset = ForestPersonDataset(
        img_dir=train_img_dir,
        label_dir=train_lbl_dir,
        img_size=img_size,
        grid_size=7,
        is_train=True
    )
    val_dataset = ForestPersonDataset(
        img_dir=val_img_dir,
        label_dir=val_lbl_dir,
        img_size=img_size,
        grid_size=7,
        is_train=False
    )

    print(f"Train Dataset Size:  {len(train_dataset)} samples")
    print(f"Val Dataset Size:    {len(val_dataset)} samples")

    if len(train_dataset) == 0:
        print("[ERROR] Train dataset is empty. Cannot start training.")
        sys.exit(1)

    train_loader = DataLoader(
        train_dataset,
        batch_size=min(batch_size, len(train_dataset)),
        shuffle=True,
        drop_last=(len(train_dataset) > batch_size)
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=min(batch_size, max(1, len(val_dataset))),
        shuffle=False
    ) if len(val_dataset) > 0 else None

    # 3. Instantiate Custom Model with Random Initialization
    model = ForestPersonNet(grid_size=7, num_classes=1).to(device)
    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"ForestPersonNet Parameters: {total_params:,} (Randomly Initialized)")

    # 4. Loss & Optimizer
    criterion = CustomDetectionLoss(lambda_coord=5.0, lambda_obj=1.0, lambda_noobj=0.5, lambda_class=1.0)
    optimizer = AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)

    # 5. Training Loop
    history = {
        "train_loss": [],
        "val_loss": [],
        "lr": []
    }

    best_val_loss = float("inf")
    start_time = time.time()

    print("\n[START] Starting Training Loop...\n")

    for epoch in range(1, epochs + 1):
        epoch_start = time.time()
        model.train()
        running_train_loss = 0.0

        for images, targets, _ in train_loader:
            images = images.to(device)
            targets = targets.to(device)

            optimizer.zero_grad()
            preds = model(images)
            loss = criterion(preds, targets)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()

            running_train_loss += loss.item() * images.size(0)

        epoch_train_loss = running_train_loss / len(train_dataset)
        history["train_loss"].append(epoch_train_loss)
        history["lr"].append(optimizer.param_groups[0]["lr"])

        # Validation Phase
        epoch_val_loss = epoch_train_loss
        if val_loader and len(val_dataset) > 0:
            model.eval()
            running_val_loss = 0.0
            with torch.no_grad():
                for val_images, val_targets, _ in val_loader:
                    val_images = val_images.to(device)
                    val_targets = val_targets.to(device)
                    val_preds = model(val_images)
                    v_loss = criterion(val_preds, val_targets)
                    running_val_loss += v_loss.item() * val_images.size(0)
            epoch_val_loss = running_val_loss / len(val_dataset)

        history["val_loss"].append(epoch_val_loss)
        scheduler.step()

        epoch_duration = time.time() - epoch_start
        print(
            f"Epoch [{epoch:03d}/{epochs:03d}] | "
            f"Train Loss: {epoch_train_loss:.4f} | "
            f"Val Loss: {epoch_val_loss:.4f} | "
            f"LR: {optimizer.param_groups[0]['lr']:.6f} | "
            f"Time: {epoch_duration:.2f}s"
        )

        # Checkpoint Saving
        if epoch_val_loss < best_val_loss:
            best_val_loss = epoch_val_loss
            torch.save(model.state_dict(), save_path)  # canonical: models/person_detector.pth

    total_training_time = time.time() - start_time
    print("-" * 70)
    print(f"[SUCCESS] Training Completed in {total_training_time:.2f}s")
    print(f"[SAVED] Best Model Saved To: {save_path} (Best Val Loss: {best_val_loss:.4f})")

    # 6. Plot & Save Training Loss Curve
    plt.figure(figsize=(9, 5))
    plt.plot(range(1, epochs + 1), history["train_loss"], label="Training Loss", color="#2a9d8f", linewidth=2)
    plt.plot(range(1, epochs + 1), history["val_loss"], label="Validation Loss", color="#e76f51", linewidth=2, linestyle="--")
    plt.title("ForestPersonNet Training & Validation Loss Curve", fontsize=14, fontweight="bold")
    plt.xlabel("Epochs", fontsize=12)
    plt.ylabel("Custom Detection Loss", fontsize=12)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(fontsize=11)
    plt.tight_layout()
    loss_curve_path = os.path.join(results_dir, "loss_curve.png")
    plt.savefig(loss_curve_path, dpi=200)
    plt.close()
    print(f"[PLOT] Loss Curve Graph Saved To: {loss_curve_path}")

    # 7. Save Training History JSON
    history_path = os.path.join(results_dir, "training_history.json")
    with open(history_path, "w") as f:
        json.dump({
            "epochs": epochs,
            "best_val_loss": best_val_loss,
            "total_time_seconds": total_training_time,
            "history": history
        }, f, indent=2)
    print(f"[LOG] Training History Saved To: {history_path}")
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train custom ForestPersonNet from scratch.")
    parser.add_argument("--epochs", type=int, default=25, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--img-size", type=int, default=224, help="Input image dimension")
    parser.add_argument("--data-dir", type=str, default="dataset/person_detection", help="Dataset directory")
    parser.add_argument("--save-path", type=str, default="models/person_detector.pth", help="Model checkpoint path")
    args = parser.parse_args()

    train_model(
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        img_size=args.img_size,
        data_dir=args.data_dir,
        save_path=args.save_path
    )
