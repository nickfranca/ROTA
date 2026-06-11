from __future__ import annotations

import os


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://prf:prf@localhost:5432/prf",
)
API_URL = os.getenv("API_URL", "http://localhost:8000")
DATA_ROOT = os.getenv("DATA_ROOT", "/data")
LOAD_CHUNK_SIZE = int(os.getenv("LOAD_CHUNK_SIZE", "25000"))
LOAD_WORKERS = int(os.getenv("LOAD_WORKERS", "1"))
