# Smart Forest Geo-Fencing & Emergency Monitoring System
# Complete Installation, Setup & Execution Guide

## 1. System Requirements & Prerequisites
- **Operating System**: Windows 10/11, Ubuntu 20.04+, or macOS
- **Python Runtime**: Python 3.10 or 3.11 (64-bit)
- **RAM**: 8 GB minimum (16 GB recommended)
- **Disk Space**: ~5 GB (including real forest image dataset)
- **Webcam**: Standard USB or integrated laptop camera (for real-time detection & face capture)
- **Browser**: Chrome, Edge, or Firefox with WebRTC support

---

## 2. Environment Setup

### 2.1 Clone or Navigate to Project Directory
```powershell
cd "d:\final MP"
```

### 2.2 Create & Activate Python Virtual Environment
```powershell
# Create virtual environment
python -m venv venv

# Activate on Windows PowerShell
.\venv\Scripts\Activate.ps1

# Activate on Linux / macOS
source venv/bin/activate
```

### 2.3 Install Dependencies
```powershell
pip install -r backend/requirements.txt
```
Key packages include:
- `torch`, `torchvision` (PyTorch Deep Learning engine)
- `flask`, `flask-sqlalchemy`, `flask-jwt-extended`, `flask-cors`, `flask-socketio`
- `shapely` (High-precision Point-in-Polygon geometric engine)
- `pymysql`, `cryptography`
- `opencv-python`, `pillow`, `scikit-learn`, `matplotlib`, `seaborn`

---

## 3. Configuration & Database Setup

### 3.1 Environment Configuration (`.env`)
The project includes a pre-configured `.env` file at the root:
```ini
# Database Selection: "sqlite" for instant plug-and-play or "mysql"
DB_TYPE=sqlite
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=smart_forest_db
DB_USER=root
DB_PASSWORD=root

# Security & Tokens
SECRET_KEY=smart-forest-geo-fencing-super-secret-key-2026
JWT_SECRET_KEY=smart-forest-jwt-secret-key-super-secure-token-2026
JWT_ACCESS_TOKEN_EXPIRES_HOURS=24

# AI Model Checkpoint Paths
PERSON_MODEL_PATH=models/person_detector.pth
FACE_MODEL_PATH=models/face_identifier.pth

# AI Decision Thresholds
PERSON_CONFIDENCE_THRESHOLD=0.40
FACE_SIMILARITY_THRESHOLD=0.65

# Server Ports
BACKEND_HOST=0.0.0.0
BACKEND_PORT=5000
```

### 3.2 Database Initialization
The application automatically creates and verifies all database tables on startup (both in SQLite and MySQL). Default forest zones and test accounts are seeded automatically.

---

## 4. Real Dataset Preparation & Audit

### 4.1 Prepare Real Datasets
Processes real photographic GoPro forest search-and-rescue imagery (`ForestPersons`) and real portraits into YOLO format:
```powershell
python ai/datasets/prepare_dataset.py
```

### 4.2 Run Dataset Integrity Audit
Audits all files on disk to confirm 100% photographic images, 0 corrupted files, 0 duplicate hashes, and complete label correspondence:
```powershell
python ai/datasets/verify_real_dataset.py
```

---

## 5. Model Training (From Scratch - Random Weights Only)

### 5.1 Train ForestPersonNet (Person Detector)
```powershell
python ai/person_detection/train.py --epochs 10 --batch-size 16
```
- Trains from Kaiming normal initialization.
- Saves best weights to `models/person_detector.pth`.
- Generates loss curve at `results/person_detection/loss_curve.png`.

### 5.2 Train ForestFaceNet (Face Identifier)
```powershell
python ai/face_identification/train.py --epochs 20 --batch-size 16
```
- Trains from random initialization with Cross-Entropy Loss.
- Saves best weights to `models/face_identifier.pth`.
- Generates accuracy and loss plots at `results/face_identification/training_curves.png`.

---

## 6. Model Evaluation

Execute evaluation on the unseen real test split:
```powershell
# Evaluate Person Detector (Precision, Recall, F1, mAP@0.5, IoU)
python ai/person_detection/evaluate.py

# Evaluate Face Identifier (Accuracy, Precision, Recall, Confusion Matrix)
python ai/face_identification/evaluate.py
```

---

## 7. Running Automated Test Suite
Run the test suite covering AI architectures, point-in-polygon geo-fencing, rule-based emergency risk engine, and JWT authentication:
```powershell
python -m unittest discover -s tests
```

---

## 8. Starting the Web Application Server

Launch the full-stack Flask application with Socket.IO:
```powershell
python backend/run.py
```
The server will bind to `http://127.0.0.1:5000`.

### Default Accounts for Demonstration
- **Administrator**: `admin@forest.gov` / `Admin@2026`
- **Field Ranger**: `ranger@forest.gov` / `Ranger@2026`
- **Registered Visitor**: `visitor@forest.gov` / `Visitor@2026`

### Key Application Portals
- **Landing Page**: `http://127.0.0.1:5000/`
- **Live AI Monitor**: `http://127.0.0.1:5000/live_monitor`
- **Face Registration**: `http://127.0.0.1:5000/face_register`
- **Interactive Geo-Fence Map**: `http://127.0.0.1:5000/geofence`
- **One-Touch Emergency SOS**: `http://127.0.0.1:5000/sos`
- **Admin Tactical Command Center**: `http://127.0.0.1:5000/admin_dashboard`
