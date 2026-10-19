import torch
import torch.nn as nn
import torch.nn.functional as F

class ConvBlock(nn.Module):
    """Basic convolutional building block with BatchNorm and LeakyReLU."""
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3, stride: int = 1, padding: int = 1):
        super().__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size, stride=stride, padding=padding, bias=False)
        self.bn = nn.BatchNorm2d(out_channels)
        self.act = nn.LeakyReLU(0.1, inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.bn(self.conv(x)))


class ResidualBlock(nn.Module):
    """Residual bottleneck block with skip connection."""
    def __init__(self, channels: int):
        super().__init__()
        mid_channels = channels // 2
        self.block = nn.Sequential(
            ConvBlock(channels, mid_channels, kernel_size=1, padding=0),
            ConvBlock(mid_channels, channels, kernel_size=3, padding=1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.block(x)


class ForestPersonNet(nn.Module):
    """
    Custom Object Detection Network built from scratch for person detection in forest environments.
    Outputs a grid of spatial detection cells.
    
    Grid size: S x S (e.g. 7x7 for 224x224 input with stride 32).
    Predictions per cell (6 values):
      [0]: tx (box center x relative to cell, 0..1)
      [1]: ty (box center y relative to cell, 0..1)
      [2]: tw (box width relative to full image, 0..1)
      [3]: th (box height relative to full image, 0..1)
      [4]: objectness confidence score (0..1)
      [5]: person class probability (0..1)
    """
    def __init__(self, grid_size: int = 7, num_classes: int = 1):
        super().__init__()
        self.grid_size = grid_size
        self.num_classes = num_classes
        self.bbox_attrs = 5 + num_classes  # 4 coords + 1 obj + num_classes = 6

        # Backbone Feature Extractor (5 progressive stages)
        self.stage1 = nn.Sequential(
            ConvBlock(3, 32, kernel_size=3, stride=1, padding=1),
            ConvBlock(32, 64, kernel_size=3, stride=2, padding=1),  # 224 -> 112
            ResidualBlock(64)
        )
        self.stage2 = nn.Sequential(
            ConvBlock(64, 128, kernel_size=3, stride=2, padding=1), # 112 -> 56
            ResidualBlock(128),
            ResidualBlock(128)
        )
        self.stage3 = nn.Sequential(
            ConvBlock(128, 256, kernel_size=3, stride=2, padding=1),# 56 -> 28
            ResidualBlock(256),
            ResidualBlock(256)
        )
        self.stage4 = nn.Sequential(
            ConvBlock(256, 512, kernel_size=3, stride=2, padding=1),# 28 -> 14
            ResidualBlock(512),
            ResidualBlock(512)
        )
        self.stage5 = nn.Sequential(
            ConvBlock(512, 512, kernel_size=3, stride=2, padding=1),# 14 -> 7
            ResidualBlock(512)
        )

        # Multi-scale detection head
        self.head = nn.Sequential(
            ConvBlock(512, 256, kernel_size=3, padding=1),
            ConvBlock(256, 128, kernel_size=3, padding=1),
            nn.Conv2d(128, self.bbox_attrs, kernel_size=1, stride=1, padding=0)
        )

        # Initialize all weights with Kaiming Normal (Random Initialization - NO PRETRAINED WEIGHTS)
        self._initialize_weights()

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="leaky_relu")
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0.0)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1.0)
                nn.init.constant_(m.bias, 0.0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        Args:
            x: Input tensor of shape (B, 3, 224, 224)
        Returns:
            Tensor of shape (B, grid_size, grid_size, 6) with values activated via sigmoid.
        """
        out = self.stage1(x)
        out = self.stage2(out)
        out = self.stage3(out)
        out = self.stage4(out)
        out = self.stage5(out)
        
        raw_preds = self.head(out)  # Shape: (B, 6, S, S)
        
        # Permute to (B, S, S, 6)
        raw_preds = raw_preds.permute(0, 2, 3, 1).contiguous()
        
        # Apply sigmoid activations for bounded outputs in [0, 1]
        activated_preds = torch.sigmoid(raw_preds)
        return activated_preds
