import os
from typing import Optional, List, Dict

from pydantic import BaseModel
from pathlib import Path


BASE_DIR = Path(os.environ.get("BASE_DIR", Path(__file__).parent))
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "Documenti"))
DB_DIR = Path(os.environ.get("DB_DIR", BASE_DIR / "data" / "chroma_db"))

LLM_MODEL = os.environ.get("LLM_MODEL", "mistral")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "intfloat/e5-large-v2")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 1500))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", 200))
TOP_K = int(os.environ.get("TOP_K", 8))
DISTANCE_THRESHOLD = float(os.environ.get("DISTANCE_THRESHOLD", 0.6))

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)

# --------- Helpers / loaders ----------
EXCLUDED_EXTS = (".md", ".csv", ".png", ".jpg", ".jpeg")

class ChatRequest(BaseModel):
    prompt: str
    top_k: Optional[int] = TOP_K
    distance_threshold: Optional[float] = DISTANCE_THRESHOLD

class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, str]] = []