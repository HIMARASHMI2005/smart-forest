import os
from datetime import timedelta
from dotenv import load_dotenv

# Load .env file from project root or backend directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(project_root, ".env"))

class Config:
    """Application configuration settings."""
    PROJECT_ROOT = project_root
    SECRET_KEY = os.getenv("SECRET_KEY", "smart-forest-secret-key-2026-prod-secure")
    
    # Database Configuration (MySQL / PyMySQL or SQLite)
    DB_TYPE = os.getenv("DB_TYPE", "mysql").lower()
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
    DB_NAME = os.getenv("DB_NAME", "smart_forest_db")
    
    if DB_TYPE == "sqlite":
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(project_root, 'smart_forest.db')}"
        SQLALCHEMY_ENGINE_OPTIONS = {}
    else:
        # SQLAlchemy URI with PyMySQL
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
        )
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_recycle": 280,
            "pool_pre_ping": True,
            "pool_size": 10,
            "max_overflow": 20
        }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT Authentication
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "smart-forest-jwt-secret-token-2026")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_HOURS", "24")))
    JWT_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"

    # AI Model File Paths (Strictly project-trained models only)
    PERSON_MODEL_PATH = os.path.join(project_root, os.getenv("PERSON_MODEL_PATH", "models/person_detector.pth"))
    FACE_MODEL_PATH = os.path.join(project_root, os.getenv("FACE_MODEL_PATH", "models/face_identifier.pth"))

    # AI Decision & Safety Thresholds
    PERSON_CONFIDENCE_THRESHOLD = float(os.getenv("PERSON_CONFIDENCE_THRESHOLD", "0.45"))
    FACE_SIMILARITY_THRESHOLD = float(os.getenv("FACE_SIMILARITY_THRESHOLD", "0.65"))
    FACE_MIN_CROPS_REQUIRED = int(os.getenv("FACE_MIN_CROPS_REQUIRED", "5"))

    # Dataset Directories
    DATASET_DIR = os.path.join(project_root, "dataset")
    FACE_DATASET_DIR = os.path.join(project_root, "dataset", "faces")
    PERSON_DATASET_DIR = os.path.join(project_root, "dataset", "person_detection")

    # Static / Upload Directories
    UPLOAD_FOLDER = os.path.join(project_root, "frontend", "static", "uploads")
    SNAPSHOTS_FOLDER = os.path.join(project_root, "frontend", "static", "uploads", "snapshots")
    FACES_UPLOAD_FOLDER = os.path.join(project_root, "frontend", "static", "uploads", "faces")
    SOS_FOLDER = os.path.join(project_root, "frontend", "static", "uploads", "sos")
