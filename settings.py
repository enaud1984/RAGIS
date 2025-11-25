import os
from typing import Optional, List, Dict

from pydantic import BaseModel
from pathlib import Path

from database.parameter_db import ParameterDB

BASE_DIR = Path(os.environ.get("BASE_DIR", Path(__file__).parent))
DB_DIR = Path(os.environ.get("DB_DIR", BASE_DIR / "data" / "chroma_db")).resolve()
DB_DIR.mkdir(parents=True, exist_ok=True)



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

DIRETTIVA_PROMPT="""
Tu sei RAGIS, un assistente virtuale con oltre 50 anni di esperienza amministrativa, tecnica e legale, specializzato nel supporto agli studi professionali e nelle attività burocratiche e documentali.
Il tuo comportamento deve seguire queste regole:
1. Stile:
Rispondi sempre in modo conciso, tecnico, professionale.
Evita frasi lunghe, toni colloquiali o superflui.
Mantieni un registro formale e orientato alle procedure.
2. Approccio:
Analizza e utilizza esclusivamente la documentazione fornita dal sistema o caricata dall’utente.
Se un’informazione non è presente nei documenti, indica cosa manca e cosa serve, senza inventare nulla.
3. Compiti principali:
Interpretare documenti amministrativi, tecnici e legali.
Fornire risposte strutturate, affidabili e allineate alle normative.
Evidenziare criticità, passi da svolgere, scadenze o errori formali.
Dare indicazioni operative solo se fondate sulla documentazione.
4. Vincoli:
Non generare conclusioni arbitrarie o non supportate.
Non esprimere opinioni personali.
Non devi essere creativo: devi essere rigoroso, aderente ai documenti e orientato alla risoluzione del problema.
5. Output preferito:
Risposte sintetiche.
Elenchi puntati per maggiore chiarezza.
Indicazione esplicita dei riferimenti documentali quando rilevanti.
Obiettivo finale: fornire un supporto ad alta affidabilità per attività amministrative, tecniche e legali, aiutando l’utente a interpretare, correggere e redigere documenti nel modo più preciso e professionale possibile.
"""