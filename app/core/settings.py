from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = BASE_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
JOBS_DIR = STORAGE_DIR / "jobs"
AUDIT_DIR = STORAGE_DIR / "audit"
MODELS_DIR = STORAGE_DIR / "models"
MONITORING_DIR = STORAGE_DIR / "monitoring"
METRICS_PATH = STORAGE_DIR / "metrics.json"

ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
FUTURE_PREDICTION_DAYS = 30
MAX_PREDICTION_RANGE_DAYS = 90

