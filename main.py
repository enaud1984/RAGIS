"""
Legal RAG Backend (Ollama) — Versione migliorata
- FastAPI async endpoints
- Singleton per Chroma/Embeddings
- Logging migliorato
- Pydantic request/response
- Maggior controllo su threshold, top_k e chunking
- Restituzione delle fonti e snippet contestuali
- Config tramite variabili d'ambiente

Prerequisiti (consigliati):
pip install fastapi uvicorn langchain chromadb unstructured pdfminer.six python-docx ollama

Config environment variables:
- DATA_DIR (default: ./Documenti)
- DB_DIR (default: ./data/chroma_db)
- LLM_MODEL (default: mistral)
- EMBED_MODEL (default: intfloat/e5-large-v2)
- CHUNK_SIZE (default: 1500)
- CHUNK_OVERLAP (default: 200)
- TOP_K (default: 8)
- DISTANCE_THRESHOLD (default: 0.6)

"""
from __future__ import annotations
import os
import glob
import hashlib
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from functools import lru_cache

from fastapi import FastAPI, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# LangChain / loaders
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
    UnstructuredEmailLoader,
    UnstructuredExcelLoader,
)
# Embeddings & LLM (wrapper to Ollama in the user's environment)
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langchain_chroma import Chroma
from langchain_unstructured import UnstructuredLoader

# --------- Config (da env o default) ----------
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL)
log = logging.getLogger("legal_rag")

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


def get_file_hash(path: Path) -> str:
    """MD5 file hash (usato per dedup)."""
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def smart_loader(path: Path):
    ext = path.suffix.lower()
    if ext == ".pdf":
        return PyPDFLoader(str(path))
    if ext in (".doc", ".docx"):
        return Docx2txtLoader(str(path))
    if ext == ".txt":
        return TextLoader(str(path), encoding="utf-8")
    if ext == ".eml":
        return UnstructuredEmailLoader(str(path))
    if ext in (".xls", ".xlsx"):
        return UnstructuredExcelLoader(str(path))
    # fallback
    return UnstructuredLoader(str(path))


def load_all_documents(base_dir: Path) -> List:
    """Carica tutti i documenti utili alla indicizzazione."""
    docs = []
    for path_str in glob.glob(str(base_dir / "**" / "*.*"), recursive=True):
        path = Path(path_str)
        if path.suffix.lower() in EXCLUDED_EXTS:
            continue
        try:
            loader = smart_loader(path)
            subdocs = loader.load()
            for d in subdocs:
                d.metadata["source"] = str(path)
            docs.extend(subdocs)
            log.info("Caricato %s (%d parti)", path.name, len(subdocs))
        except Exception as e:
            log.warning("Errore caricando %s: %s", path, e)
    return docs


# --------- Singleton factories for embeddings & vectordb ----------
@lru_cache(maxsize=1)
def get_embeddings():
    log.info("Inizializzo embeddings: %s", EMBED_MODEL)
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL)


@lru_cache(maxsize=1)
def get_vector_db():
    """Crea e ritorna un'istanza Chroma singleton.
    Nota: Chroma puede caricare da persist_directory.
    """
    log.info("Apro/creo Chroma DB in: %s", DB_DIR)
    embeddings = get_embeddings()
    return Chroma(persist_directory=str(DB_DIR), embedding_function=embeddings)


# --------- Indicizzazione incrementale ----------
def build_vector_db() -> Dict[str, str]:
    log.info("Start indicizzazione incrementale...")
    vectordb = get_vector_db()

    # recupera metadati esistenti per dedup basata su hash
    try:
        existing = vectordb.get()
    except Exception:
        existing = {}
    existing_hashes = set(m.get("hash") for m in existing.get("metadatas", []) if m.get("hash"))

    all_docs = load_all_documents(DATA_DIR)
    valid_docs = [d for d in all_docs if not d.metadata.get("source", "").lower().endswith(EXCLUDED_EXTS)]

    new_docs = []
    for doc in valid_docs:
        p = Path(doc.metadata.get("source"))
        if not p.exists():
            continue
        h = get_file_hash(p)
        if h in existing_hashes:
            continue
        doc.metadata["hash"] = h
        new_docs.append(doc)

    if not new_docs:
        log.info("Nessun nuovo documento da indicizzare.")
        return {"message": "Nessun nuovo documento."}

    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks = splitter.split_documents(new_docs)

    ids = []
    for i, c in enumerate(chunks):
        root_hash = c.metadata.get("hash", "nohash")
        c.metadata["chunk_index"] = i
        ids.append(f"{root_hash}-{i}")

    vectordb.add_documents(documents=chunks, ids=ids)

    # Persistenza corretta per la nuova API
    try:
        vectordb._client.persist()
    except Exception:
        log.warning("Persist automatico non disponibile; forse non necessario.")


    msg = f"Indicizzati {len(new_docs)} nuovi documenti (tot chunk: {len(chunks)})."
    log.info(msg)
    return {"message": msg}


# --------- RAG query ----------
def decide_from_db(prompt: str, threshold: float = 0.7, top_k: int = 10) -> Tuple[bool, str]:
    vectordb = get_vector_db()

    # 1) Prompt troppo breve → niente RAG
    if len(prompt.split()) < 4:
        return False, "Prompt troppo breve per una ricerca affidabile."

    # 2) Threshold dinamico
    if len(prompt.split()) < 6:
        threshold = min(threshold, 0.35)

    results = vectordb.similarity_search_with_score(prompt, k=top_k)
    if not results:
        return False, "DB vuoto o nessun match."

    # Ordina per distanza
    results.sort(key=lambda x: x[1])

    # 3) Richiedi almeno 2 match forti
    close_matches = [(doc, dist) for doc, dist in results if dist <= threshold]

    if len(close_matches) < 2:
        return False, "Match insufficienti per usare il RAG."

    return True, "Match soddisfacenti nei documenti."



def query_rag(question: str, top_k: int = TOP_K, distance_threshold: float = DISTANCE_THRESHOLD) -> Tuple[str, List[Dict[str, str]]]:
    log.info("Prompt: %s", question)
    vectordb = get_vector_db()
    results = vectordb.similarity_search_with_score(question, k=top_k)
    if not results:
        raise RuntimeError("Nessun risultato dalla ricerca vettoriale.")

    # filtra e ordina
    results = sorted(results, key=lambda x: x[1])
    filtered = [(doc, dist) for (doc, dist) in results if dist <= distance_threshold]

    if not filtered:
        return ("", [])

    # costruisco contesto limitato (es. primi 5 chunk)
    max_chunks = 5
    context_parts = []
    sources = []
    for i, (doc, dist) in enumerate(filtered[:max_chunks]):
        snippet = doc.page_content
        context_parts.append(f"Fonte: {doc.metadata.get('source')} (distanza: {dist:.3f})\n{snippet}")
        sources.append({"source": doc.metadata.get("source"), "distance": f"{dist:.3f}", "chunk_index": str(doc.metadata.get("chunk_index", "-"))})

    context = "\n\n---\n\n".join(context_parts)

    system_prompt = (
        """Sei un assistente legale italiano, cordiale ed educato. Usa solo le informazioni presenti nel contesto per formulare la risposta. 
        Se non c'è abbastanza informazione indica chiaramente che non è possibile rispondere e suggerisci cosa fornire."""
    )

    full_prompt = f"{system_prompt}CONTESTO:\n{context}\n\nDOMANDA:\n{question}\n\nRisposta concisa e puntuale:" 

    llm = ChatOllama(model=LLM_MODEL, temperature=0)
    resp = llm.invoke(full_prompt)
    answer_text = getattr(resp, "content", str(resp))

    return answer_text, sources


# --------- FastAPI app ----------
app = FastAPI(title="Legal RAG Backend (Ollama) — Improved")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/", tags=["meta"])
def root():
    return {"message": "Legal RAG Backend (Ollama) attivo. Usa /chat o /reindex"}


@app.post("/chat/", response_model=ChatResponse, tags=["chat"])
def chat(body: ChatRequest = Body(...)):
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt vuoto")

    match, msg = decide_from_db(body.prompt, threshold=body.distance_threshold or DISTANCE_THRESHOLD, top_k=body.top_k or TOP_K)
    if not match:
        return ChatResponse(answer="Non ho trovato informazioni rilevanti nei documenti.", sources=[])

    try:
        answer, sources = query_rag(body.prompt, top_k=body.top_k or TOP_K, distance_threshold=body.distance_threshold or DISTANCE_THRESHOLD)
        if not answer:
            return ChatResponse(answer="Non ho abbastanza informazioni nei documenti per rispondere. Specifica contesto o carica documenti.", sources=sources)
        return ChatResponse(answer=answer, sources=sources)
    except Exception as e:
        log.exception("Errore query_rag")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/reindex/", tags=["admin"])
def reindex():
    try:
        result = build_vector_db()
        return {"message": result.get("message", "OK")}
    except Exception as e:
        log.exception("Errore indicizzazione")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/debug_db/", tags=["admin"])
def debug_db():
    try:
        vectordb = get_vector_db()
        all_data = vectordb.get()
        num_docs = len(all_data.get("ids", []))
        sample_meta = all_data.get("metadatas", [])[:5]
        return {"documenti": num_docs, "metadati_sample": sample_meta}
    except Exception as e:
        log.exception("Errore debug DB")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    log.info("Avvio server uvicorn su 0.0.0.0:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
