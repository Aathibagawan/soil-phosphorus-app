"""Runtime configuration (all overridable via environment variables)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", BASE_DIR / "artifacts"))
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", BASE_DIR / "frontend"))

# SQLite by default (zero-config). For persistence across restarts on free hosts,
# point this at a hosted Postgres, e.g. postgresql://user:pass@host/db
_db_url = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'predictions.db'}")
if _db_url.startswith("postgres://"):                      # Render/Heroku style URL
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
DATABASE_URL = _db_url

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

MAX_WINDOW_ROWS = int(os.getenv("MAX_WINDOW_ROWS", "5000"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(2 * 1024 * 1024)))
MAX_HISTORY_PER_CLIENT = int(os.getenv("MAX_HISTORY_PER_CLIENT", "500"))
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))   # 0 disables
