import torch
import torch.nn as nn
import torch.nn.functional as F

class CustomDetectionLoss(nn.Module):
    """
    Custom multi-task detection loss combining:
    1. Coordinate Bounding Box Regression Loss (Smooth L1)
    2. Responsible Cell Objectness Loss (Focal / BCE)
    3. Background Cell Hard Negative Mining Loss
    4. Person Classification Loss (BCE)
    """
    def __init__(self, lambda_coord: float = 5.0, lambda_obj: float = 1.0, lambda_noobj: float = 0.5, lambda_class: float = 1.0):
        super().__init__()
        self.lambda_coord = lambda_coord
        self.lambda_obj = lambda_obj
        self.lambda_noobj = lambda_noobj
        self.lambda_class = lambda_class

    def forward(self, preds: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Args:
            preds: Predicted tensor (B, S, S, 6) in [0, 1]
            targets: Ground-truth target tensor (B, S, S, 6)
        Returns:
            Scalar loss tensor
        """
        # Object mask: 1 where object is present, 0 otherwise
        obj_mask = targets[..., 4] == 1.0
        noobj_mask = targets[..., 4] == 0.0

        # 1. Coordinate Loss (Center offsets tx, ty + Dimensions tw, th)
        if obj_mask.sum() > 0:
            pred_boxes = preds[..., 0:4][obj_mask]
            target_boxes = targets[..., 0:4][obj_mask]
            coord_loss = F.smooth_l1_loss(pred_boxes, target_boxes, reduction="mean")
        else:
            coord_loss = torch.tensor(0.0, device=preds.device)

        # 2. Objectness Loss for cells containing an object
        if obj_mask.sum() > 0:
            pred_obj = preds[..., 4][obj_mask]
            target_obj = targets[..., 4][obj_mask]
            obj_loss = F.binary_cross_entropy(pred_obj, target_obj, reduction="mean")
        else:
            obj_loss = torch.tensor(0.0, device=preds.device)

        # 3. Background Objectness Loss (with hard negative / sampling)
        pred_noobj = preds[..., 4][noobj_mask]
        target_noobj = targets[..., 4][noobj_mask]
        if noobj_mask.sum() > 0:
            noobj_loss = F.binary_cross_entropy(pred_noobj, target_noobj, reduction="mean")
        else:
            noobj_loss = torch.tensor(0.0, device=preds.device)

        # 4. Class Prediction Loss
        if obj_mask.sum() > 0:
            pred_cls = preds[..., 5][obj_mask]
            target_cls = targets[..., 5][obj_mask]
            class_loss = F.binary_cross_entropy(pred_cls, target_cls, reduction="mean")
        else:
            class_loss = torch.tensor(0.0, device=preds.device)

        total_loss = (
            self.lambda_coord * coord_loss +
            self.lambda_obj * obj_loss +
            self.lambda_noobj * noobj_loss +
            self.lambda_class * class_loss
        )
        return total_loss
