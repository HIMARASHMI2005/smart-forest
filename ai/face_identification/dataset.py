import os
import glob
import numpy as np
import cv2
from torch.utils.data import Dataset
from ai.face_identification.preprocessing import preprocess_face_for_model, augment_face


class FaceDataset(Dataset):
    """
    PyTorch Dataset for ForestFaceNet face identification training.
    
    Expects directory structure:
        dataset/faces/
            person_001/
                01.jpg  02.jpg  ...
            person_002/
                01.jpg  ...
    
    Returns preprocessed face tensor of shape (3, 112, 112) and integer class label.
    Applies augmentation during training to increase effective dataset size.
    """

    def __init__(self, root_dir: str, is_train: bool = True, augment: bool = True):
        self.root_dir = root_dir
        self.is_train = is_train
        self.augment = augment and is_train

        self.samples = []      # List of (face_tensor, label_index)
        self.class_names = []  # List of identity folder names (sorted)
        self.class_to_idx = {}

        self._scan_dataset()

    def _scan_dataset(self):
        """Scans dataset directory and collects all face image paths with labels."""
        if not os.path.exists(self.root_dir):
            raise FileNotFoundError(f"Face dataset directory not found: {self.root_dir}")

        identity_dirs = sorted([
            d for d in os.listdir(self.root_dir)
            if os.path.isdir(os.path.join(self.root_dir, d))
        ])

        if len(identity_dirs) == 0:
            raise ValueError(f"No identity subdirectories found in: {self.root_dir}")

        self.class_names = identity_dirs
        self.class_to_idx = {name: idx for idx, name in enumerate(self.class_names)}

        print(f"[FaceDataset] Found {len(self.class_names)} registered identities.")

        for person_dir in self.class_names:
            person_path = os.path.join(self.root_dir, person_dir)
            label = self.class_to_idx[person_dir]

            img_paths = []
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp"):
                img_paths.extend(glob.glob(os.path.join(person_path, ext)))
                img_paths.extend(glob.glob(os.path.join(person_path, ext.upper())))

            for img_path in img_paths:
                img_bgr = cv2.imread(img_path)
                if img_bgr is None:
                    continue

                face_tensor = preprocess_face_for_model(
                    cv2.resize(img_bgr, (112, 112))
                )
                self.samples.append((face_tensor, label))

                # Augmentation during training
                if self.augment:
                    aug_variants = augment_face(cv2.resize(img_bgr, (112, 112)))
                    for aug_tensor in aug_variants:
                        self.samples.append((aug_tensor, label))

        print(f"[FaceDataset] Total samples loaded: {len(self.samples)} (augmentation={'ON' if self.augment else 'OFF'})")

    def num_classes(self):
        return len(self.class_names)

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        import torch
        face_tensor, label = self.samples[idx]
        return torch.from_numpy(face_tensor).float(), torch.tensor(label, dtype=torch.long)
