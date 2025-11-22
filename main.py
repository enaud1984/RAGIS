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

import asyncio
import shutil
from contextlib import asynccontextmanager

import aiocron
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database.parameter_db import ParameterDB
from logger_ragis.rag_log import RagLog
from fastapi import FastAPI, Body, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from settings import *
from rag.embeddings import get_vector_db
from rag.indexing import build_vector_db
from rag.rag_query import decide_from_db, query_rag

from database.migration import run_migrations

log = RagLog.get_logger("Ragis")


async def reindex_notturno(app_: FastAPI):
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

app.add_middleware(CORSMiddleware,
                   allow_origins=["*"],
                   allow_methods=["*"],
                   allow_headers=["*"])

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
async def chat(request:Request, body: ChatRequest = Body(...)):
    if request.app.state.reindexing:
        return {
            "reindex":True,
            "testo": "Il sistema sta aggiornando il database. "
                        "Riprova tra qualche minuto."}

    params = resolve_params()
    top_k= body.top_k if body.top_k is not None else params["top_k"]
    distance_threshold = (
        body.distance_threshold
        if body.distance_threshold is not None
        else params["distance_threshold"]
    )

    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt vuoto")

    match, msg = decide_from_db(body.prompt, threshold=body.distance_threshold or distance_threshold, top_k=body.top_k or top_k)
    if not match:
        return ChatResponse(answer="Non ho trovato informazioni rilevanti nei documenti.", sources=[])

    try:
        answer, sources = query_rag(body.prompt, top_k=body.top_k or top_k, distance_threshold=body.distance_threshold or distance_threshold)
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


@app.post("/upload/", tags=["admin"])
async def upload_files(request: Request, files: list[UploadFile] = File(...)):
    saved_files = []
    params = resolve_params()
    data_dir = params["data_dir"]
    if request.app.state.reindexing:
        return {
            "reindex":True,
            "testo": "Il sistema sta aggiornando il database. "
                        "Riprova tra qualche minuto."}

    for file in files:
        dest_path = Path(data_dir) / file.filename
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        saved_files.append(file.filename)
        log.info(f"File caricato: {dest_path}")

    return {
        "messagio": "Upload completato.",
        "files_salvati": saved_files
    }

if __name__ == "__main__":
    import uvicorn
    run_migrations()  # Esegue creazione DB
    """
    parameter_db = ParameterDB()
    parameter_db.set("llm_model", "mistral", descrizione="Modello LLM da utilizzare")
    parameter_db.set("embed_model", "intfloat/e5-large-v2", descrizione="Modello di embedding da utilizzare")
    parameter_db.set("chunk_size", 1500, tipo="number", descrizione="Dimensione chunk documenti")
    parameter_db.set("chunk_overlap", 200, tipo="number",descrizione="Overlap chunk")
    parameter_db.set("top_k", 8, tipo="number", descrizione="Top K chunk")
    parameter_db.set("distance_threshold", 0.6, tipo="decimale",descrizione="Soglia di similarità")
    parameter_db.set("EXCLUDED_EXTS",".md, .csv, .png, .jpg, .jpeg", tipo="tupla",descrizione="Cartella documenti")
    parameter_db.set("DATA_DIR","Documenti", tipo="string",descrizione="Cartella documenti")
    """
    log.info("Avvio server uvicorn su 0.0.0.0:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
