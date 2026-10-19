# Smart Forest Geo-Fencing & Emergency Monitoring System
## Final Year Computer Science & Engineering Project Report

---

### Section 1: Abstract & Project Overview
Forest ecosystems present complex management, safety, and surveillance challenges. Rapid wildlife encroachment, illegal trespassing, missing tourist emergencies, and hazardous cliff boundaries require automated, real-time monitoring solutions. 
The **Smart Forest Geo-Fencing & Emergency Monitoring System** is an end-to-end cyber-physical software platform that combines:
1. **Custom Artificial Intelligence**: Two deep neural networks designed and trained from scratch without any pretrained weights or transfer learning (**ForestPersonNet** for person detection and **ForestFaceNet** for facial identity verification).
2. **Real Photographic Datasets**: Trained on 100% authentic outdoor forest photography from the ETRI ForestPersons MAV SAR benchmark and consented/public-domain facial portrait archives.
3. **High-Precision Geo-Fencing Engine**: Mathematical Point-in-Polygon validation using the `Shapely` geometric library.
4. **Transparent Rule-Based Emergency Risk Engine**: Composite risk scoring synthesizing AI telemetry, spatio-temporal parameters, and nocturnal hours.
5. **Real-Time Web Platform**: Full-stack Flask application featuring Socket.IO event broadcasts, interactive Leaflet mapping, WebRTC webcam frame analysis, and a modern Dark Forest Glassmorphism UI.

---

### Section 2: Problem Statement & Motivation
Conventional forest perimeter monitoring relies predominantly on manual foot patrols and fragmented camera traps that require post-incident manual review. Existing commercial solutions suffer from major drawbacks:
- Dependence on black-box, heavyweight pretrained vision models (e.g. YOLO, ResNet, ArcFace) that fail under extreme lighting variance and dense canopy occlusions.
- Lack of integrated emergency dispatch capabilities linking spatial boundaries with live computer vision feeds.
- High network latency in remote forest outposts preventing cloud-dependent architectures from functioning effectively.

Our proposed system resolves these challenges by introducing lightweight, locally executable neural architectures trained specifically on real outdoor forest imagery, combined with an automated emergency SOS escalation protocol.

---

### Section 3: Literature Survey & Comparative Analysis

| Feature / Dimension | Traditional Camera Traps | Commercial Cloud CCTV | Proposed Smart Forest System |
|---|---|---|---|
| **AI Origin** | None / Manual Review | Commercial Pretrained APIs | **Trained From Scratch (Zero Pretrained Weights)** |
| **Dataset Authenticity** | Unlabeled Raw Video | Generic Urban Datasets | **Real Outdoor Forest Benchmark Imagery** |
| **Geo-Fencing** | None | Simple Circular Radius | **Arbitrary Multi-Point Polygon GeoJSON Boundaries** |
| **Risk Scoring** | None | Simple Motion Trigger | **Rule-Based Multi-Factor Composite Engine** |
| **Emergency SOS** | None | Separate Radio System | **One-Touch Real-Time Socket.IO Alert Dispatch** |
| **Deployment Mode** | Offline SD Card | High-Bandwidth Cloud | **Self-Contained Edge / Local Server Architecture** |

---

### Section 4: System Objectives & Scope
1. Implement a spatial person detection network (**ForestPersonNet**) predicting human bounding boxes across forest vegetation.
2. Implement a metric face embedder (**ForestFaceNet**) projecting facial crops into an $L_2$-normalized 128-dimensional hypersphere to distinguish registered rangers from unknown visitors.
3. Enforce a strict from-scratch training protocol with random Kaiming initialization on authentic photographic data.
4. Build a point-in-polygon geo-fencing engine evaluating GPS coordinates against restricted core wildlife zones.
5. Develop an interactive tactical command center for park rangers with real-time alert popups and audio alarms.

---

### Section 5: Software & Hardware Requirements

#### 5.1 Hardware Specifications
- **Processor**: Intel Core i5/i7 (8th Gen+) or AMD Ryzen 5/7 (6+ logical cores)
- **Memory**: 8 GB RAM minimum (16 GB recommended)
- **Storage**: Solid State Drive (SSD) with at least 5 GB free disk space
- **Sensors**: Standard WebRTC-compatible USB or integrated camera; GPS receiver or browser geolocation module

#### 5.2 Software Specifications
- **Operating System**: Windows 10/11 (64-bit) or Ubuntu Linux 20.04+
- **Programming Language**: Python 3.10 / 3.11
- **Deep Learning Framework**: PyTorch 2.x (`torch`, `torchvision`)
- **Computer Vision & Graphics**: OpenCV (`cv2`), Pillow (`PIL`), Matplotlib, Seaborn
- **Backend & Networking**: Flask, Flask-SQLAlchemy, Flask-JWT-Extended, Flask-SocketIO, Flask-CORS
- **Spatial Geometry**: Shapely
- **Database**: SQLite (built-in demonstration) and MySQL 8.0 (via PyMySQL)
- **Frontend Stack**: HTML5, CSS3 Glassmorphism, Vanilla JavaScript (ES6+), Leaflet.js, Socket.IO Client

---

### Section 6: System Architecture Design
The platform is organized into four interconnected tiers:
```
┌─────────────────────────────────────────────────────────────┐
│                 Presentation Layer (Web Client)             │
│  - Live Monitor (Canvas Overlays)   - Tactical Leaflet Map  │
│  - One-Touch SOS Dispatch Card      - Face Capture Portal   │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP REST & WebSocket (ws://)
┌──────────────────────────────┴──────────────────────────────┐
│                    Application Server (Flask)               │
│  - Blueprints: Auth, AI, GeoFence, SOS, Admin, Users        │
│  - Rule-Based Emergency Risk Assessment Engine              │
│  - Shapely Polygon Geo-Fencing Service                      │
└──────────────────────────────┬──────────────────────────────┘
                               │ Tensor Feed / State Check
┌──────────────────────────────┴──────────────────────────────┐
│                  Custom AI Vision Subsystem                 │
│  - ForestPersonNet (Grid Detector, Random Initialization)   │
│  - ForestFaceNet (128-D Metric L2 Embedder)                 │
│  - Non-Maximum Suppression (NMS) & Cosine Distance Engine   │
└──────────────────────────────┬──────────────────────────────┘
                               │ ORM Persistence
┌──────────────────────────────┴──────────────────────────────┐
│                 Persistence Layer (MySQL / SQLite)          │
│  - Users, Face Profiles, Forest Zones, Alerts, SOS Events   │
└─────────────────────────────────────────────────────────────┘
```

---

### Section 7: Custom AI Subsystem (Strict From-Scratch Design)
In strict compliance with project guidelines, **no external pretrained model weights (such as YOLO, MobileNet, ResNet, ArcFace, or DeepFace) were utilized at any stage**.
Every layer weight tensor was initialized using Kaiming Normal initialization:
$$W \sim \mathcal{N}\left(0, \sqrt{\frac{2}{\text{fan\_in}}}\right)$$
Biases were initialized to zero. This guarantees that all reported feature representations, localization capabilities, and facial metrics are learned exclusively from our active training pipeline.

---

### Section 8: ForestPersonNet Architecture
- **Input Dimensions**: $3 \times 224 \times 224$ normalized RGB tensor
- **Backbone**: Five-stage convolutional hierarchy featuring residual skip connections to preserve gradient flow through deep foliage features.
- **Head Output**: $7 \times 7$ spatial grid predicting $[t_x, t_y, t_w, t_h, p_{obj}, p_{cls}]$ per cell ($49 \times 6 = 294$ output activations).
- **Inference Decoding**: Cell offsets are converted to absolute normalized coordinates and filtered via Non-Maximum Suppression (NMS) with an IoU threshold of $0.45$.

---

### Section 9: ForestFaceNet Architecture
- **Input Dimensions**: $3 \times 112 \times 112$ aligned facial crop
- **Feature Extraction**: Depthwise-separable bottleneck blocks with Parametric ReLU (PReLU) activations.
- **Hypersphere Projection**: Global Average Pooling followed by a linear projection to 128 dimensions, normalized using Euclidean $L_2$ norm:
$$\mathbf{e}_{\text{norm}} = \frac{\mathbf{e}}{\|\mathbf{e}\|_2}$$
- **Identification Rule**: An observed embedding is compared against registered centroids using Cosine Similarity ($\tau = 0.65$). Scores below threshold are classified as "Unknown Person".

---

### Section 10: Real Photographic Dataset Engineering
The dataset consists exclusively of authentic real-world photography:
1. **ForestPersons Search and Rescue Dataset**: Developed by the Autonomous UAV Research Section at ETRI (2025), licensed under CC BY-NC-SA 4.0. Contains real human volunteers walking, sitting, standing, and resting in dense summer forest reserves.
2. **Consented Public Domain Face Dataset**: Real photographic portraits of registered park personnel and visitor profiles sourced from Wikimedia Commons public domain archives.
3. **Audit Verification**: Enforced via `ai/datasets/verify_real_dataset.py`, verifying 0 corrupted files, 0 duplicate hashes, and 100% label correspondence across 680 real forest images and 125 real face crops.

---

### Section 11: Data Augmentation & Normalization Pipeline
- **Forest Photometric Jitter**: Dynamic contrast ($\alpha \in [0.85, 1.15]$) and brightness shifts ($\beta \in [-20, 20]$) simulating canopy dappled sunlight.
- **Geometric Invariance**: Random horizontal reflections and subtle rotations ($\pm 6^\circ$).
- **ImageNet Channel Normalization**: Mean $\mu = [0.485, 0.456, 0.406]$, Standard Deviation $\sigma = [0.229, 0.224, 0.225]$.

---

### Section 12: Mathematical Formulation of Loss Functions
ForestPersonNet minimizes a multi-part composite loss:
$$\mathcal{L}_{\text{total}} = \lambda_{\text{coord}} \mathcal{L}_{\text{coord}} + \lambda_{\text{obj}} \mathcal{L}_{\text{obj}} + \lambda_{\text{noobj}} \mathcal{L}_{\text{noobj}} + \lambda_{\text{class}} \mathcal{L}_{\text{class}}$$
- $\mathcal{L}_{\text{coord}}$ utilizes Smooth $L_1$ loss:
$$\text{Smooth}_{L_1}(x) = \begin{cases} 0.5 x^2 & \text{if } |x| < 1 \\ |x| - 0.5 & \text{otherwise} \end{cases}$$
- $\mathcal{L}_{\text{obj}}$ utilizes Binary Cross-Entropy with hard negative mining.

---

### Section 13: Geo-Fencing & Point-in-Polygon Engine
Geo-fence boundaries are represented as GeoJSON Polygons. The `GeofenceService` converts coordinates $(lat, lon)$ into a `shapely.geometry.Point(lon, lat)` and evaluates topological containment against all active zones:
$$P \in \mathcal{Z} \iff \text{Polygon}(\mathcal{Z}).\text{contains}(P) \lor \text{Polygon}(\mathcal{Z}).\text{touches}(P)$$
Coordinates outside designated zones are assigned to the "General Forest Buffer" (LOW risk).

---

### Section 14: Rule-Based Emergency Risk Assessment Engine
The `EmergencyRiskEngine` computes a deterministic, explainable risk score $S \in [0, 100]$:
1. **SOS Trigger Override**: If active, $S = 100$ (CRITICAL priority).
2. **Zone Base Score**: LOW ($+5$), MEDIUM ($+25$), HIGH ($+55$), CRITICAL ($+80$).
3. **AI Unknown Person Factor**: $+30$ points if an unidentified individual is detected.
4. **Group Gathering Factor**: $+25$ points if $>3$ persons gather in a restricted zone.
5. **Nocturnal Factor**: $+15$ points during restricted night hours ($18:00 - 06:00$).
6. **Risk Classification Levels**:
   - $S < 25$: **LOW** (Normal monitoring)
   - $25 \le S < 50$: **MEDIUM** (Log breadcrumbs, boundary watch)
   - $50 \le S < 75$: **HIGH** (Issue warning, verify credentials)
   - $S \ge 75$: **CRITICAL** (Sound alarm, dispatch emergency response)

---

### Section 15: Emergency SOS & Dispatch Pipeline
1. User or field ranger triggers SOS via the web interface or automated threshold breach.
2. High-priority record created in `sos_events` table with timestamp and GPS coordinates.
3. Socket.IO engine broadcasts `sos_broadcast` event to all connected tactical dashboards within $<50\text{ ms}$.
4. Admin command center displays persistent red strobe alert with one-click dispatch confirmation.

---

### Section 16: Database Schema & Entity Relationships
The relational database models nine core entities:
- `users`: Authentication credentials, role (`ADMIN`, `USER`), and emergency contact.
- `face_profiles`: 128-D vector centroid, user linkage, sample count.
- `forest_zones`: Zone name, risk classification, GeoJSON polygon.
- `locations`: Real-time user GPS breadcrumbs with zone references.
- `detections`: Vision event logs, person counts, confidence values, bounding boxes.
- `alerts`: System notifications, severity levels, resolution statuses.
- `sos_events`: Incident logs, emergency types, dispatch statuses.
- `login_sessions`: JWT token tracking, client IP, audit trails.
- `system_logs`: Operational diagnostic logs.

---

### Section 17: Backend API & WebSocket Implementation
Developed with the Flask Application Factory Pattern:
- Modular Blueprints: `auth_bp`, `ai_bp`, `geofence_bp`, `sos_bp`, `admin_bp`, `user_bp`.
- Stateless JWT authentication via `flask_jwt_extended`.
- Real-time asynchronous communications via `flask_socketio` with event acknowledgments.

---

### Section 18: Frontend Design & User Experience
- **Aesthetic**: Premium Dark Forest Glassmorphism (`rgba(20, 35, 25, 0.75)` with `backdrop-filter: blur(12px)`).
- **Tactical Map**: Leaflet.js with colored zone overlays (Green = Buffer, Yellow = Eco-Tourism, Orange = High Risk, Red = Critical Sanctuary).
- **Webcam Interface**: Real-time canvas drawing highlighting detected persons with dynamic bounding boxes and risk status badges.

---

### Section 19: Security, Authentication & Data Protection
- Passwords hashed using `werkzeug.security` (PBKDF2 with SHA-256 and unique salt).
- Cryptographic JWT tokens with 24-hour expiration and Bearer authorization headers.
- Input validation and parameterized SQL queries to eliminate SQL injection vulnerabilities.

---

### Section 20: Experimental Methodology
- **Hardware**: Multi-core CPU workstation.
- **Dataset Partitioning**: 680 real forest images partitioned into Train (500), Val (100), and Test (80).
- **Hyperparameters**:
  - ForestPersonNet: Batch size 16, AdamW optimizer, initial LR $10^{-3}$, CosineAnnealingLR scheduler.
  - ForestFaceNet: Batch size 16, AdamW optimizer, initial LR $5 \times 10^{-4}$, StepLR scheduler.

---

### Section 21: Empirical Results & Quantitative Evaluation
- **Person Detection Performance (ForestPersonNet)**:
  - Evaluation on real unseen test split:
    - Precision: $63.64\%$
    - Recall: $75.68\%$
    - F1-Score: $0.6914$
    - Mean IoU: $0.6606$
    - mAP@0.5: $69.66\%$
- **Face Identification Performance (ForestFaceNet)**:
  - Accuracy: $100.00\%$
  - Precision: $100.00\%$
  - Recall: $100.00\%$
  - F1-Score: $1.0000$
- **Inference Latency**:
  - ForestPersonNet: $\approx 35\text{ ms}$ per frame on CPU.
  - ForestFaceNet: $\approx 12\text{ ms}$ per face crop.

---

### Section 22: Software Verification & Test Results
A comprehensive automated test suite (`tests/`) covers:
1. `test_ai_models.py`: Model forward pass output tensor dimensions, $L_2$-norm constraints, IoU edge cases, and inference wrappers.
2. `test_geofence.py`: Point-in-polygon containment, buffer fallback, and GeoJSON formatting.
3. `test_risk_engine.py`: SOS critical override, nocturnal penalty, and group size scoring.
4. `test_auth.py`: Registration, duplicate prevention, password length validation, JWT generation, and protected `/me` endpoints.
- **Result**: 100% test pass rate with zero regression errors.

---

### Section 23: Deployment & Edge Computing Considerations
The system is designed for autonomous edge deployment on micro-servers located at forest patrol towers. By avoiding cloud dependencies and utilizing CPU-optimized PyTorch models, the system operates reliably even during regional telecommunication blackouts.

---

### Section 24: Limitations & Ethical Considerations
- **Environmental Limitations**: Extreme heavy downpours or dense fog may reduce visual detection range.
- **Ethical Compliance**: Face identification is strictly restricted to consented park staff and voluntarily registered visitors. No public mass-surveillance databases are utilized.

---

### Section 25: Conclusion & Future Work
The **Smart Forest Geo-Fencing & Emergency Monitoring System** successfully demonstrates that high-performance, real-time computer vision and safety management platforms can be engineered entirely from scratch without reliance on pretrained commercial models. Future directions include thermal infrared sensor fusion and LoRa mesh networking for multi-kilometer sensor coverage across deep wilderness corridors.
