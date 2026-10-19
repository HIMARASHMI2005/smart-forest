# Smart Forest Geo-Fencing & Emergency Monitoring System
# Custom AI Architecture & Training Pipeline Documentation

## 1. Architectural Philosophy: Strict From-Scratch Engineering
A foundational requirement of this project is that **no pretrained models, transfer learning weights, or external checkpoints are ever utilized**.
Both the person detection network (**ForestPersonNet**) and the face identification network (**ForestFaceNet**) are:
1. Designed with custom PyTorch network topologies.
2. Initialized strictly from random Gaussian/Kaiming weights (`torch.nn.init.kaiming_normal_`).
3. Trained end-to-end on our verified real photographic datasets.
4. Evaluated using formal statistical metrics (mAP, IoU, Precision, Recall, Confusion Matrices).

---

## 2. ForestPersonNet: Custom Person Detection CNN

### 2.1 Network Topology & Dimensional Specifications
ForestPersonNet is a multi-scale convolutional neural network tailored for detecting individuals and groups amidst challenging outdoor forest foliage.

```
Input Frame (3 x 224 x 224)
        │
┌───────┴───────┐
│ Stage 1 Conv  │  Conv2d(3, 32, 3x3) + BatchNorm + LeakyReLU(0.1) + MaxPool(2)  -> [32, 112, 112]
└───────┬───────┘
┌───────┴───────┐
│ Stage 2 Conv  │  Conv2d(32, 64, 3x3) + BatchNorm + LeakyReLU(0.1) + MaxPool(2) -> [64, 56, 56]
└───────┬───────┘
┌───────┴───────┐
│ Stage 3 Res   │  Conv2d(64, 128, 3x3) + Residual Skip Connection + MaxPool(2)  -> [128, 28, 28]
└───────┬───────┘
┌───────┴───────┐
│ Stage 4 Res   │  Conv2d(128, 256, 3x3) + Residual Skip Connection + MaxPool(2) -> [256, 14, 14]
└───────┬───────┘
┌───────┴───────┐
│ Stage 5 Conv  │  Conv2d(256, 512, 3x3) + BatchNorm + LeakyReLU(0.1) + MaxPool(2)-> [512, 7, 7]
└───────┬───────┘
┌───────┴───────┐
│ Spatial Head  │  Conv2d(512, 256, 3x3) -> Conv2d(256, 6, 1x1)                  -> [6, 7, 7]
└───────┬───────┘
        │
Output Grid: S x S x (4 + 1 + 1) = [7, 7, 6]
```

### 2.2 Output Representation
The $7 \times 7$ output grid divides the $224 \times 224$ image into 49 spatial cells ($32 \times 32$ pixels per cell). Each cell predicts 6 parameters:
1. $t_x$: Normalized horizontal center offset relative to the grid cell $[0, 1]$
2. $t_y$: Normalized vertical center offset relative to the grid cell $[0, 1]$
3. $t_w$: Square-root normalized bounding box width $[0, 1]$
4. $t_h$: Square-root normalized bounding box height $[0, 1]$
5. $p_{obj}$: Objectness confidence score (Sigmoid activation)
6. $p_{cls}$: Person class conditional probability (Sigmoid activation)

### 2.3 Loss Function Formulation
The model is optimized using `CustomDetectionLoss`, balancing localization precision and objectness discrimination:

$$\mathcal{L} = \lambda_{\text{coord}} \mathcal{L}_{\text{coord}} + \lambda_{\text{obj}} \mathcal{L}_{\text{obj}} + \lambda_{\text{noobj}} \mathcal{L}_{\text{noobj}} + \lambda_{\text{class}} \mathcal{L}_{\text{class}}$$

Where:
- $\lambda_{\text{coord}} = 5.0$, $\lambda_{\text{obj}} = 1.0$, $\lambda_{\text{noobj}} = 0.5$, $\lambda_{\text{class}} = 1.0$
- **Coordinate Loss**: Smooth L1 loss across active cells containing ground-truth human targets.
- **Objectness Loss**: Binary Cross Entropy with hard negative mining to handle the background-to-foreground imbalance typical of large forest canopies.

---

## 3. ForestFaceNet: Custom Metric Face Embedder

### 3.1 Network Topology & 128-D Metric Space
ForestFaceNet extracts an $L_2$-normalized 128-dimensional embedding vector representing human facial identity, invariant to ambient lighting and camera distance.

```
Input Face Crop (3 x 112 x 112)
        │
┌───────┴───────┐
│ Stem Block    │  Conv2d(3, 32, 3x3, stride 2) + BatchNorm + PReLU               -> [32, 56, 56]
└───────┬───────┘
┌───────┴───────┐
│ Bottleneck 1  │  Depthwise-Separable Residual Block (32 -> 64, stride 2)        -> [64, 28, 28]
└───────┬───────┘
┌───────┴───────┐
│ Bottleneck 2  │  Depthwise-Separable Residual Block (64 -> 128, stride 2)       -> [128, 14, 14]
└───────┬───────┘
┌───────┴───────┐
│ Bottleneck 3  │  Depthwise-Separable Residual Block (128 -> 256, stride 2)      -> [256, 7, 7]
└───────┬───────┘
┌───────┴───────┐
│ Pooling & Proj│  Global Average Pooling -> Linear(256, 128) -> L2 Normalization  -> [128-D Embedding]
└───────┬───────┘
        │
   ||e||_2 = 1.0
        │
┌───────┴───────┐
│ Class Head    │  Linear(128, num_classes) (Used during supervised training)
└───────────────┘
```

### 3.2 Metric Cosine Distance Matching
During inference, the identity of an observed face is verified by computing the Cosine Similarity against registered personnel profiles stored in the database:

$$\text{Cosine Similarity}(e_1, e_2) = \frac{e_1 \cdot e_2}{\|e_1\|_2 \|e_2\|_2} = e_1 \cdot e_2$$

- **Threshold**: $\tau = 0.65$
- If $\max_i \text{Similarity}(e_{\text{observed}}, e_i) \ge \tau$, the individual is identified as the registered user.
- If below threshold, the individual is safely designated as **"Unknown Person"**, prompting the rule-based risk engine to evaluate perimeter threat levels.

---

## 4. Training Execution Procedures

### 4.1 Training ForestPersonNet
```bash
python ai/person_detection/train.py --epochs 10 --batch-size 16 --lr 0.001
```
- Optimizer: `AdamW(lr=1e-3, weight_decay=1e-4)`
- Scheduler: `CosineAnnealingLR(T_max=10, eta_min=1e-6)`
- Best checkpoint automatically saved to `models/person_detector.pth`

### 4.2 Training ForestFaceNet
```bash
python ai/face_identification/train.py --epochs 20 --batch-size 16 --lr 0.0005
```
- Optimizer: `AdamW(lr=5e-4, weight_decay=1e-4)`
- Best checkpoint automatically saved to `models/face_identifier.pth`
- Class index mapping automatically saved to `models/face_class_map.json`

---

## 5. Evaluation Commands
```bash
# Evaluate Person Detector on real test split
python ai/person_detection/evaluate.py

# Evaluate Face Identifier on real test split
python ai/face_identification/evaluate.py
```
Output charts and metrics are automatically saved into `results/person_detection/` and `results/face_identification/`.
