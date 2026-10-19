import torch
import torch.nn as nn
import torch.nn.functional as F


class FaceConvBlock(nn.Module):
    def __init__(self, in_ch, out_ch, stride=1):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, stride=stride, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.PReLU(out_ch)
        )

    def forward(self, x):
        return self.block(x)


class FaceResBlock(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(channels, channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(channels),
            nn.PReLU(channels),
            nn.Conv2d(channels, channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(channels)
        )
        self.act = nn.PReLU(channels)

    def forward(self, x):
        return self.act(x + self.block(x))


class ForestFaceNet(nn.Module):
    """
    Custom Face Identification CNN built from scratch with random initialization.
    Architecture produces a 128-dimensional L2-normalized face embedding vector.
    
    This model is NEVER initialized from pretrained FaceNet, ArcFace, or any
    external weights. All weights use Kaiming Normal initialization.
    
    Input:  (B, 3, 112, 112) face images
    Output: (B, 128) L2-normalized face embeddings
    """

    def __init__(self, embedding_dim: int = 128, num_classes: int = None):
        super().__init__()
        self.embedding_dim = embedding_dim
        self.num_classes = num_classes  # Classification head for training

        # Feature Extraction Backbone
        self.backbone = nn.Sequential(
            FaceConvBlock(3, 32, stride=1),       # 112x112
            FaceConvBlock(32, 64, stride=2),       # 56x56
            FaceResBlock(64),
            FaceConvBlock(64, 128, stride=2),      # 28x28
            FaceResBlock(128),
            FaceResBlock(128),
            FaceConvBlock(128, 256, stride=2),     # 14x14
            FaceResBlock(256),
            FaceResBlock(256),
            FaceConvBlock(256, 512, stride=2),     # 7x7
            FaceResBlock(512),
        )

        # Embedding head: Global Average Pool ? FC ? 128-D embedding
        self.embedding_head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),    # (B, 512, 1, 1)
            nn.Flatten(),              # (B, 512)
            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.PReLU(256),
            nn.Dropout(0.4),
            nn.Linear(256, embedding_dim)   # (B, 128)
        )

        # Identity classification head (used only during training)
        self.classifier = None
        if num_classes is not None and num_classes > 0:
            self.classifier = nn.Linear(embedding_dim, num_classes)

        # Random initialization ? NO pretrained weights
        self._initialize_weights()

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='leaky_relu')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.BatchNorm2d) or isinstance(m, nn.BatchNorm1d):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Linear):
                nn.init.xavier_normal_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, x: torch.Tensor):
        """
        Args:
            x: (B, 3, 112, 112)
        Returns:
            embedding: (B, 128) L2-normalized
            logits: (B, num_classes) if classifier is attached, else None
        """
        features = self.backbone(x)
        embedding = self.embedding_head(features)
        # L2 normalization: ensures ||embedding||? = 1
        embedding = F.normalize(embedding, p=2, dim=1)

        logits = None
        if self.classifier is not None:
            logits = self.classifier(embedding)

        return embedding, logits
