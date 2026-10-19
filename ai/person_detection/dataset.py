import os
import glob
import random
import numpy as np
from PIL import Image, ImageEnhance
import torch
from torch.utils.data import Dataset
import torchvision.transforms as transforms

class ForestPersonDataset(Dataset):
    """
    PyTorch Dataset for Forest Person Detection.
    Loads images and YOLO-style bounding box annotation files (.txt).
    Transforms annotations into spatial grid targets of shape (S, S, 6).
    """
    def __init__(
        self,
        img_dir: str,
        label_dir: str,
        img_size: int = 224,
        grid_size: int = 7,
        is_train: bool = True
    ):
        self.img_dir = img_dir
        self.label_dir = label_dir
        self.img_size = img_size
        self.grid_size = grid_size
        self.is_train = is_train

        # Supported image extensions
        valid_exts = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp")
        self.img_paths = []
        for ext in valid_exts:
            self.img_paths.extend(glob.glob(os.path.join(img_dir, ext)))
            self.img_paths.extend(glob.glob(os.path.join(img_dir, ext.upper())))
        
        self.img_paths.sort()

        # Base normalization transform
        self.normalize = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    def __len__(self) -> int:
        return len(self.img_paths)

    def _apply_augmentations(self, image: Image.Image, boxes: list):
        """Applies forest-specific photometric and geometric augmentations."""
        # 1. Random Brightness & Contrast
        if random.random() > 0.5:
            factor = random.uniform(0.7, 1.3)
            image = ImageEnhance.Brightness(image).enhance(factor)
        if random.random() > 0.5:
            factor = random.uniform(0.7, 1.3)
            image = ImageEnhance.Contrast(image).enhance(factor)

        # 2. Random Horizontal Flip
        if random.random() > 0.5:
            image = image.transpose(Image.FLIP_LEFT_RIGHT)
            flipped_boxes = []
            for box in boxes:
                cls_id, xc, yc, w, h = box
                flipped_boxes.append((cls_id, 1.0 - xc, yc, w, h))
            boxes = flipped_boxes

        return image, boxes

    def __getitem__(self, idx: int):
        img_path = self.img_paths[idx]
        image = Image.open(img_path).convert("RGB")
        
        # Load corresponding label file
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        label_path = os.path.join(self.label_dir, f"{base_name}.txt")

        boxes = []
        if os.path.exists(label_path):
            with open(label_path, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        cls_id = int(float(parts[0]))
                        xc, yc, w, h = map(float, parts[1:5])
                        boxes.append((cls_id, xc, yc, w, h))

        # Apply training augmentations
        if self.is_train and len(boxes) > 0:
            image, boxes = self._apply_augmentations(image, boxes)

        # Resize image
        image = image.resize((self.img_size, self.img_size))
        img_tensor = self.normalize(image)

        # Build ground-truth grid target (S, S, 6)
        target = torch.zeros((self.grid_size, self.grid_size, 6), dtype=torch.float32)

        for box in boxes:
            cls_id, xc, yc, w, h = box
            
            # Clip coordinates
            xc = min(max(xc, 0.0), 0.999)
            yc = min(max(yc, 0.0), 0.999)
            w = min(max(w, 0.001), 1.0)
            h = min(max(h, 0.001), 1.0)

            # Determine responsible grid cell
            gx = int(xc * self.grid_size)
            gy = int(yc * self.grid_size)

            tx = (xc * self.grid_size) - gx
            ty = (yc * self.grid_size) - gy

            # Mark cell as containing object
            target[gy, gx, 0] = tx
            target[gy, gx, 1] = ty
            target[gy, gx, 2] = w
            target[gy, gx, 3] = h
            target[gy, gx, 4] = 1.0  # objectness
            target[gy, gx, 5] = 1.0  # person class probability

        return img_tensor, target, img_path
