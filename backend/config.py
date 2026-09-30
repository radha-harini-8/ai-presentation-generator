"""
Central configuration loaded from environment variables (.env).
Never hard-code secrets here - everything sensitive comes from the environment.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (one level above backend/)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    # --- Gemini ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # --- Embeddings / RAG ---
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "800"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "120"))
    TOP_K_CHUNKS: int = int(os.getenv("TOP_K_CHUNKS", "6"))

    # --- Database ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")

    # --- Storage ---
    UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
    GENERATED_DIR: Path = Path(os.getenv("GENERATED_DIR", str(BASE_DIR / "generated_presentations")))
    VECTOR_STORE_DIR: Path = Path(os.getenv("VECTOR_STORE_DIR", str(BASE_DIR / "vector_store")))

    # --- Upload limits ---
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20"))
    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

    # --- Server ---
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # --- CORS ---
    ALLOWED_ORIGINS = [
        o.strip() for o in os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:8000,http://127.0.0.1:8000"
        ).split(",") if o.strip()
    ]


settings = Settings()

# Make sure storage directories exist at import time
for _dir in (settings.UPLOAD_DIR, settings.GENERATED_DIR, settings.VECTOR_STORE_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
