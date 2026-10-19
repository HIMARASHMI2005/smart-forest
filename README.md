# 🌲 Smart Forest Geo-Fencing & Emergency Monitoring System
> **Final Year CSE Project — Automated Wilderness Safety, Custom Vision AI & Real-Time Incident Response**

---

## 🌟 Key Highlights
- **100% Real Photographic Dataset**: Sourced from the official ETRI **ForestPersons** MAV Search and Rescue benchmark and verified public-domain portrait archives. Zero AI-generated humans, zero synthetic drawings.
- **Strictly From-Scratch AI Engineering**: Both **ForestPersonNet** and **ForestFaceNet** are built with custom PyTorch network topologies and trained from random Kaiming weights with **ZERO pretrained weights, ZERO transfer learning, and ZERO external checkpoints**.
- **High-Precision Geo-Fencing**: Polygon-based point-in-polygon containment engine powered by `Shapely`.
- **Explainable Rule-Based Emergency Risk Engine**: Synthesizes AI detections, spatial zones, group size, and nocturnal hours.
- **Real-Time Bidirectional Web Platform**: Flask application featuring Socket.IO live alarms, Leaflet mapping, WebRTC webcam analysis, and dark forest glassmorphism aesthetics.

---

## 🏗️ System Architecture

```
[ Webcam / Drone Stream ]       [ GPS Coordinates ]
            │                           │
            ▼                           ▼
  [ ForestPersonNet ]           [ Shapely Geo-Fence ]
   (Custom CNN Grid)             (Point-in-Polygon)
            │                           │
            └───────────┬───────────────┘
                        ▼
         [ Emergency Risk Engine ]
          (Deterministic Rules)
                        │
                        ▼
      [ Flask Backend & Socket.IO ]
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
 [ User Live Portal ]        [ Tactical Command Center ]
```

---

## 🚀 Quick Start Guide

### 1. Environment Setup
```powershell
# Create & activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install required dependencies
pip install -r backend/requirements.txt
```

### 2. Dataset Verification & Audit
Audit the authentic real photographic dataset:
```powershell
python ai/datasets/verify_real_dataset.py
```
Outputs verified disk file statistics:
- **680** Real Forest Person Detection Images (Train: 500, Val: 100, Test: 80)
- **825** Individual Person Bounding Box Annotations
- **125** Real Photographic Face Crops across 5 Registered Identities
- **0** Corrupted, duplicate, or missing labels

### 3. Run Automated Tests
```powershell
python -m unittest discover -s tests
```
Verifies AI forward pass dimensions, $L_2$-norm constraints, geo-fencing containment, risk engine rules, and authentication workflows.

### 4. Start the Application
```powershell
python backend/run.py
```
Open **`http://127.0.0.1:5000`** in your browser.

---

## 🧭 Application Portals & Credentials

### Default Accounts
| Role | Email | Password |
|---|---|---|
| **Administrator** | `admin@forest.gov` | `Admin@2026` |
| **Field Ranger** | `ranger@forest.gov` | `Ranger@2026` |
| **Registered Visitor** | `visitor@forest.gov` | `Visitor@2026` |

### Key URLs
- **Landing Page**: `http://127.0.0.1:5000/`
- **Live AI Detection**: `http://127.0.0.1:5000/live_monitor`
- **Face Registration**: `http://127.0.0.1:5000/face_register`
- **Interactive Geo-Fence Map**: `http://127.0.0.1:5000/geofence`
- **One-Touch Emergency SOS**: `http://127.0.0.1:5000/sos`
- **Admin Command Center**: `http://127.0.0.1:5000/admin_dashboard`

---

## 🧠 Custom AI Vision Models (From Scratch)

### ForestPersonNet (Person Detection)
- **Architecture**: 5-stage convolutional feature extractor with residual skip connections.
- **Output**: $7 \times 7 \times 6$ spatial grid predicting $[t_x, t_y, t_w, t_h, p_{obj}, p_{cls}]$ per cell.
- **Training Command**:
  ```powershell
  python ai/person_detection/train.py --epochs 10 --batch-size 16
  ```
- **Evaluation Command**:
  ```powershell
  python ai/person_detection/evaluate.py
  ```

### ForestFaceNet (Face Identification)
- **Architecture**: Deep convolutional network with depthwise-separable residual bottlenecks.
- **Output**: $L_2$-normalized 128-dimensional embedding vector ($\|e\|_2 = 1$).
- **Matching**: Cosine Similarity against registered centroids with threshold $\tau = 0.65$.
- **Training Command**:
  ```powershell
  python ai/face_identification/train.py --epochs 20 --batch-size 16
  ```
- **Evaluation Command**:
  ```powershell
  python ai/face_identification/evaluate.py
  ```

---

## 📁 Repository Structure
```
├── ai/
│   ├── datasets/               # Real dataset utilities (verify, prepare, validate, stats)
│   ├── face_identification/    # ForestFaceNet model, train, evaluate, inference
│   └── person_detection/       # ForestPersonNet model, loss, train, evaluate, inference
├── backend/
│   ├── app/
│   │   ├── models/             # SQLAlchemy ORM models (User, Zone, Alert, SOS, etc.)
│   │   ├── routes/             # Blueprints (auth, ai, geofence, sos, admin, user)
│   │   ├── services/           # RiskEngine, GeofenceService, NotificationService
│   │   └── config.py           # Database & JWT configurations
│   └── run.py                  # Flask-SocketIO entry point
├── dataset/
│   ├── person_detection/       # Real images & labels (train, val, test) + metadata.csv
│   └── faces/                  # Real photographic face crops for registered identities
├── docs/                       # Comprehensive documentation suite
│   ├── AI_TRAINING.md          # Model architectures & training manual
│   ├── DATASET.md              # Dataset provenance, ethics & audit report
│   ├── API.md                  # REST & Socket.IO API specification
│   ├── SETUP.md                # Installation and execution guide
│   └── PROJECT_REPORT.md       # 25-section complete CSE project report
├── frontend/
│   ├── static/css/             # Dark forest glassmorphism design
│   ├── static/js/              # WebRTC, Leaflet, Socket.IO, Canvas overlays
│   └── templates/              # HTML5 responsive user & admin templates
├── models/                     # Saved model checkpoints (.pth) & class maps
├── results/                    # Loss curves, confusion matrices, evaluation metrics
└── tests/                      # Automated unit and integration test suite
```

---

## 📄 License & Attribution
- **Application Code**: Educational Final Year CSE Project.
- **ForestPersons Dataset**: ETRI Autonomous UAV Research Section (CC BY-NC-SA 4.0).
- **Face Portrait Archives**: Public Domain & Creative Commons via Wikimedia Commons.
