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

"""

from __future__ import annotations

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
    Esegue il reindex.
    Durante il reindex le API vengono bloccate dal middleware.
    """
    log.info("==> INIZIO REINDEX NOTTURNO — API BLOCCATE")
    app_.state.reindexing = True

    try:
        await asyncio.to_thread(build_vector_db)
        log.info("==> REINDEX COMPLETATO")
    except Exception as e:
        log.exception("Errore nel reindex: %s", e)
    finally:
        app_.state.reindexing = False
        log.info("==> API RIATTIVATE")


@asynccontextmanager
async def lifespan(app_: FastAPI):
    app_.state.reindexing = False

    # Salvi il job nella app state
    cron_job = aiocron.crontab("0 3 * * *", func=reindex_notturno, args=(app_,))
    app_.state.cron_job = cron_job

    log.info("Reindex giornaliero programmato alle 03:00")

    yield   # <- FastAPI inizia qui a servire richieste

    # Shutdown
    app_.state.cron_job.stop()
    log.info("Crontab fermato correttamente")


app = FastAPI(title="RAG Server", lifespan=lifespan)

app.add_middleware(CORSMiddleware,
                   allow_origins=["*"],
                   allow_methods=["*"],
                   allow_headers=["*"])

FRONTEND_DIR = Path(__file__).parent / "frontend_dist"
static_dir = FRONTEND_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")

@app.get("/")
def serve_frontend():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Frontend non buildato. Esegui: npm run build"}


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
async def debug_db():
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
    parameter_db = ParameterDB()
    parameter_db.set("llm_model", "mistral", descrizione="Modello LLM da utilizzare")
    parameter_db.set("embed_model", "intfloat/e5-large-v2", descrizione="Modello di embedding da utilizzare")
    parameter_db.set("chunk_size", 1500, tipo="number", descrizione="Dimensione chunk documenti")
    parameter_db.set("chunk_overlap", 200, tipo="number",descrizione="Overlap chunk")
    parameter_db.set("top_k", 8, tipo="number", descrizione="Top K chunk")
    parameter_db.set("distance_threshold", 0.6, tipo="decimale",descrizione="Soglia di similarità")
    parameter_db.set("EXCLUDED_EXTS",".md, .csv, .png, .jpg, .jpeg", tipo="tupla",descrizione="Cartella documenti")
    parameter_db.set("DATA_DIR","Documenti", tipo="string",descrizione="Cartella documenti")

    log.info("Avvio server uvicorn su 0.0.0.0:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
