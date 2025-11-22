import os
from typing import Optional, List, Dict

from pydantic import BaseModel
from pathlib import Path

from database.parameter_db import ParameterDB

BASE_DIR = Path(os.environ.get("BASE_DIR", Path(__file__).parent))
DB_DIR = Path(os.environ.get("DB_DIR", BASE_DIR / "data" / "chroma_db")).resolve()
DB_DIR.mkdir(parents=True, exist_ok=True)

"""
LLM_MODEL = os.environ.get("LLM_MODEL", "mistral")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "intfloat/e5-large-v2")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 1500))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", 200))
TOP_K = int(os.environ.get("TOP_K", 8))
DISTANCE_THRESHOLD = float(os.environ.get("DISTANCE_THRESHOLD", 0.6))
EXCLUDED_EXTS = (".md", ".csv", ".png", ".jpg", ".jpeg")
"""
class LoginRequest(BaseModel):
    username: str
    password: str

class UserRequest(BaseModel):
    username: str
    password: str
    ruolo:str

class ChatRequest(BaseModel):
    prompt: str
    top_k: Optional[int] = None
    distance_threshold: Optional[float] = None

class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, str]] = []

def resolve_params():
    db = ParameterDB()
    params = {}
    # LLM
    params["llm_model"] = db.get("llm_model", "mistral")
    # Embeddings
    params["embed_model"] = db.get("embed_model", "intfloat/e5-large-v2")
    # Chunking
    params["chunk_size"] = int(db.get("chunk_size", 1500))
    params["chunk_overlap"] = int(db.get("chunk_overlap", 200))
    # RAG Parameters
    params["top_k"] = int(db.get("top_k", 8))
    params["distance_threshold"] = float(db.get("distance_threshold", 0.6))
    # Extensions (string → tuple)
    excluded_str = db.get("excluded_exts", ".md,.csv,.png,.jpg,.jpeg")
    params["excluded_exts"] = tuple(
        ext.strip() for ext in excluded_str.split(",") if ext.strip()
    )
    params["cron_reindex"] = db.get("cron_reindex", "0 3 * * *")  # Default: ogni giorno alle 3 AM
    data_dir = Path(db.get("DATA_DIR", "Documenti")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    params["data_dir"] = data_dir


    return params