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
import sys
from contextlib import asynccontextmanager
from pathlib import Path
import requests

import aiocron
from fastapi import FastAPI, Body, HTTPException, Request, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import StreamingResponse

from auth import hash_password, verify_password, create_jwt, validate_token
from database.connection import DBConnection
from database.migration import run_migrations
from logger_ragis.rag_log import RagLog
from rag.embeddings import get_vector_db
from rag.indexing import build_vector_db
from rag.ingestion import ingest_documents
from rag.rag_query import decide_from_db, query_rag, query_rag_stream
from settings import *

log = RagLog.get_logger("Ragis")

#per Pyinstaller usa la cartella temporanea creata
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent

async def reindex_notturno(app_: FastAPI):
    """
    Esegue il reindex.
    Durante il reindex le API vengono bloccate dal middleware.
    """
    log.info("==> INIZIO REINDEX NOTTURNO — API BLOCCATE")
    app_.state.reindexing = True

    try:
        # Usa chunking dinamico (default=True) per migliore qualità dei chunk
        await asyncio.to_thread(build_vector_db, FakeRequest(app_), use_dynamic_chunking=True)
        log.info("==> REINDEX COMPLETATO CON CHUNKING DINAMICO")
    except Exception as e:
        log.exception("Errore nel reindex: %s", e)
    finally:
        app_.state.reindexing = False
        log.info("==> API RIATTIVATE")

class FakeRequest:
    def __init__(self, app):
        self.app = app

@asynccontextmanager
async def lifespan(app_: FastAPI):
    app_.state.reindexing = False
    # Esegui le migrazioni e assicurati che l'utente di default esista
    # Questo permette di avere l'utente 'admin' con password 'admin'
    await asyncio.to_thread(run_migrations)

    app_.state.params = resolve_params()
    
    # === INGESTION AL STARTUP ===
    log.info("==> INIZIO INGESTION AL STARTUP")
    try:
        ingest_result = await asyncio.to_thread(
            ingest_documents,
            source_dir=Path("Documenti"),
            ingested_dir=Path("Documenti_ingested"),
            deterministic=True
        )
        log.info(f"Ingestion completata: {ingest_result['files_ingested']} file ingesti, "
                f"{ingest_result['files_skipped']} skipped")
    except Exception as e:
        log.exception(f"Errore ingestion startup: {e}")
    
    # === BUILD VETTORIALE INIZIALE ===
    log.info("==> INIZIO BUILD DATABASE VETTORIALE (CHUNKING DINAMICO)")
    try:
        await asyncio.to_thread(build_vector_db, FakeRequest(app_), use_dynamic_chunking=True)
        log.info("==> BUILD DATABASE VETTORIALE COMPLETATO")
    except Exception as e:
        log.exception(f"Errore build database vettoriale: {e}")
    
    # Salvi il job nella app state
    cron_reindex = app_.state.params["cron_reindex"]
    cron_job = aiocron.crontab(cron_reindex, func=reindex_notturno, args=(app_,))
    app_.state.cron_job = cron_job

    log.info("Reindex giornaliero programmato alle 03:00")

    yield  # <- FastAPI inizia qui a servire richieste

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
async def chat(request: Request, body: ChatRequest = Body(...), payload: dict = Depends(validate_token)):
    if request.app.state.reindexing:
        return {
            "reindex": True,
            "testo": "Il sistema sta aggiornando il database. "
                     "Riprova tra qualche minuto."}
    log.info(f"Richiesta chat da utente: {payload.get('username')}, testo: {body.prompt[:50]}...")
    params = request.app.state.params
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt vuoto")

    top_k = body.top_k if body.top_k is not None else params["top_k"]
    distance_threshold = (
        body.distance_threshold
        if body.distance_threshold is not None
        else params["distance_threshold"]
    )
    llm_model = body.llm_model if body.llm_model is not None else params["llm_model"]

    match, msg = decide_from_db(request,body.prompt, threshold=body.distance_threshold or distance_threshold,
                                top_k=body.top_k or top_k)
    answer_init=""
    if not match:
        answer_init = "Non ho trovato informazioni rilevanti nei documenti."

    try:
        answer, sources = query_rag(request,body.prompt, top_k=body.top_k or top_k,
                                    distance_threshold=body.distance_threshold or distance_threshold,
                                    llm_model=body.llm_model or llm_model)
        if not answer:
            return ChatResponse(
                answer="Non ho abbastanza informazioni nei documenti per rispondere. Specifica contesto o carica documenti.",
                sources=sources)

        return ChatResponse(answer=f"{answer_init} {answer}", sources=sources)
    except Exception as e:
        log.exception("Errore query_rag")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/stream", response_model=ChatResponse, tags=["chat_stream"])
async def chat_stream(request: Request, body: ChatRequest = Body(...), payload: dict = Depends(validate_token)):
    if request.app.state.reindexing:
        async def blocked():
            yield "Sistema in aggiornamento. Riprova più tardi."
        return StreamingResponse(blocked(), media_type="text/plain")

    log.info(f"Richiesta chat da utente: {payload.get('username')}, testo: {body.prompt[:50]}...")
    params = request.app.state.params
    if not body.prompt.strip():
        async def empty():
            yield "Prompt vuoto."
        return StreamingResponse(empty(), media_type="text/plain")
    top_k = body.top_k if body.top_k is not None else params["top_k"]
    distance_threshold = (
        body.distance_threshold
        if body.distance_threshold is not None
        else params["distance_threshold"]
    )
    llm_model = body.llm_model if body.llm_model is not None else params["llm_model"]

    match, msg = decide_from_db(request,body.prompt, threshold=body.distance_threshold or distance_threshold,
                                top_k=body.top_k or top_k)
    answer_init=""
    if not match:
        answer_init = "Non ho trovato informazioni rilevanti nei documenti."

    async def event_generator():
        try:
            # Prefisso risposta (se serve)
            if answer_init:
                yield answer_init

            async for chunk in query_rag_stream(
                request,
                question=body.prompt,
                top_k=top_k,
                distance_threshold=distance_threshold,
                llm_model=llm_model,
            ):
                yield chunk

        except asyncio.CancelledError:
            log.info("Stream interrotto dall'utente (STOP)")
            return

        except Exception as e:
            log.exception("Errore query_rag_stream")
            yield f"\nErrore durante la generazione della risposta: {e}"

    return StreamingResponse(
        event_generator(),
        media_type="text/plain; charset=utf-8",
    )


@app.get("/reindex/", tags=["admin"])
def reindex(request: Request, payload: dict = Depends(validate_token)):
    try:
        # Usa chunking dinamico (default=True per migliore qualità)
        result = build_vector_db(request, use_dynamic_chunking=True)
        return {"message": result.get("message", "OK"), "strategy": "dynamic_chunking"}
    except Exception as e:
        log.exception("Errore indicizzazione")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/debug_db/", )
def debug_db(request:Request):
    try:
        vectordb = get_vector_db(request)
        all_data = vectordb.get()
        num_docs = len(all_data.get("ids", []))
        sample_meta = all_data.get("metadatas", [])[:5]
        return {"documenti": num_docs, "metadati_sample": sample_meta}
    except Exception as e:
        log.exception("Errore debug DB")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_parameters", tags=["admin"])
def get_parameters(request:Request, payload: dict = Depends(validate_token)):
    return request.app.state.params


@app.post("/save_parameters", tags=["admin"])
def save_parameters(body: dict = Body(...), payload: dict = Depends(validate_token)):
    try:
        parameter_db = ParameterDB()
        for key, value in body.items():
            parameter_db.set(key, value)
        return {"message": "Parametri salvati con successo"}
    except Exception as e:
        log.exception("Errore salvataggio parametri")
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/get_models",tags=["admin"])
def get_models(request:Request,payload: dict = Depends(validate_token)):
    try:
        parameter=request.app.state.params
        modelli_generici=parameter["Models"]
        resp = requests.get("http://localhost:11434/api/tags")
        resp.raise_for_status()
        modelli_installati = [m["name"] for m in resp.json().get("models", [])]
        result = []
        for model in modelli_generici:
            result.append({
                "name": model,
                "installed": model in modelli_installati
            })

        return {"models": result}
    except Exception as e:
        log.exception(f"Errore recupero modelli: {e}")
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/download_model")
def download_model(payload: dict,user_dict: dict = Depends(validate_token)):
    try:
        requests.post("http://localhost:11434/api/pull", json={"name": payload.get('model_name')})
    except Exception as e:
        log.exception(f"Errore download modello: {e}")
        raise HTTPException(status_code=401, detail=str(e))
    return {"message": f"Modello '{payload.get('model_name')}' scaricato e impostato come attivo."}


@app.post("/login")
def login(body: LoginRequest):
    try:
        conn = DBConnection()
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE username = ?", (body.username,))
        row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=401, detail="Credenziali non valide - nessun utente trovato")

        stored_hash = row["password_hash"]

        if not verify_password(body.password, stored_hash):
            raise HTTPException(status_code=401, detail="Credenziali non valide - password")

        ruolo = row["ruolo"]

        token = create_jwt(body.username, ruolo)
        return {
            "token": token,
            "username": body.username,
            "ruolo": ruolo
        }

    except Exception as e:
        log.exception(f"Errore login utente {body.username}: {e}")
        raise HTTPException(status_code=500, detail="Errore durante il login")
    finally:
        conn.close()



@app.post("/registrazione", tags=["admin"])
def register(body: UserRequest, payload: dict = Depends(validate_token)):
    try:
        # Solo admin può creare nuovi utenti
        ruolo_richiedente = payload.get("ruolo", "").lower()
        if ruolo_richiedente != "admin":
            raise HTTPException(status_code=403, detail="Solo admin può creare utenti")

        conn = DBConnection()
        cur = conn.cursor()

        hashed = hash_password(body.password)

        log.info(f"Tentativo di registrazione: username={body.username}, ruolo={body.ruolo}")

        cur.execute("""
            INSERT INTO users (username, password_hash, ruolo)
            VALUES (?, ?, ?)
        """, (body.username, hashed, body.ruolo))

        conn.conn.commit()
        log.info(f"Utente {body.username} creato con successo")
        return {"messaggio": "Registrazione completata"}
    except Exception as e:
        log.exception(f"Errore nella creazione utente {body.username}: {e}")
        raise HTTPException(status_code=400, detail="Username già esistente")
    finally:
        conn.close()


@app.get("/lista-utenti", tags=["admin"])
def lista_utenti(payload: dict = Depends(validate_token)):
    try:
        # Solo admin può leggere la lista utenti
        ruolo_richiedente = payload.get("ruolo", "").lower()
        if ruolo_richiedente != "admin":
            raise HTTPException(status_code=403, detail="Solo admin può accedere alla lista utenti")

        conn = DBConnection()
        cur = conn.cursor()

        cur.execute("SELECT id, username, password_hash, ruolo FROM users")
        utenti = cur.fetchall()

        # Trasformazione in dizionari
        result = [
            {"id": row[0], "username": row[1], "password_hash": row[2], "ruolo": row[3]}
            for row in utenti
        ]

        return {"utenti": result}

    except Exception as e:
        log.exception(f"Errore durante la lettura utenti: {e}")
        raise HTTPException(status_code=500, detail="Errore server interno")
    finally:
        conn.close()

@app.put("/aggiorna-utente/{user_id}", tags=["admin"])
def aggiorna_utente(user_id: int, body: UserRequest, payload: dict = Depends(validate_token)):
    try:
        # Solo admin
        ruolo_richiedente = payload.get("ruolo", "").lower()
        if ruolo_richiedente != "admin":
            raise HTTPException(status_code=403, detail="Solo admin può aggiornare utenti")

        conn = DBConnection()
        cur = conn.cursor()

        # Costruzione dinamica dei campi aggiornabili
        update_fields = []
        values = []

        if body.username:
            update_fields.append("username = ?")
            values.append(body.username)

        if body.ruolo:
            update_fields.append("ruolo = ?")
            values.append(body.ruolo)

        if body.password:
            hashed = hash_password(body.password)
            update_fields.append("password_hash = ?")
            values.append(hashed)

        if not update_fields:
            raise HTTPException(status_code=400, detail="Nessun campo da aggiornare")

        values.append(user_id)

        query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"

        cur.execute(query, tuple(values))
        conn.conn.commit()

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Utente non trovato")

        return {"messaggio": "Utente aggiornato correttamente"}

    except Exception as e:
        log.exception(f"Errore aggiornamento utente {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Errore durante aggiornamento")
    finally:
        conn.close()

@app.delete("/cancella-utente/{user_id}", tags=["admin"])
def cancella_utente(user_id: int, payload: dict = Depends(validate_token)):
    try:
        # Solo admin
        ruolo_richiedente = payload.get("ruolo", "").lower()
        if ruolo_richiedente != "admin":
            raise HTTPException(status_code=403, detail="Solo admin può cancellare utenti")

        conn = DBConnection()
        cur = conn.cursor()

        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.conn.commit()

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Utente non trovato")

        return {"messaggio": "Utente cancellato con successo"}

    except Exception as e:
        log.exception(f"Errore cancellazione utente {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Errore durante cancellazione utente")
    finally:
        conn.close()

@app.post("/ingest/", tags=["admin"])
def ingest(request: Request, payload: dict = Depends(validate_token)):
    """
    Ingestion Layer - Normalizza, valida, deduplica documenti.
    
    Processi:
    - Normalizzazione nomi file
    - Validazione 6-point check (esistenza, hidden, formato, size, vuoto, encoding)
    - Deduplicazione content-based (SHA256)
    - Organizzazione (by_format/, by_date/)
    - Generazione manifest.jsonl + metadata.json
    
    Output:
    - Documenti_ingested/ (normalizzato)
    - manifest.jsonl (14 campi per file)
    - metadata.json (statistiche)
    """
    if request.app.state.reindexing:
        return {
            "success": False,
            "message": "Il sistema sta eseguendo reindex. Riprova tra qualche minuto."
        }
    
    try:
        params = request.app.state.params
        source_dir = params.get("data_dir", "Documenti")
        ingested_dir = "Documenti_ingested"
        
        log.info(f"Inizio ingestion: {source_dir} → {ingested_dir}")
        
        result = ingest_documents(
            source_dir=source_dir,
            ingested_dir=ingested_dir,
            deterministic=True
        )
        
        log.info(f"Ingestion completata: {result['files_ingested']} file ingested, "
                f"{result['files_skipped']} skipped, {result['files_corrupted']} corrupted")
        
        return {
            "success": result.get("success", True),
            "total_files_found": result.get("total_files_found", 0),
            "files_ingested": result.get("files_ingested", 0),
            "files_skipped": result.get("files_skipped", 0),
            "files_corrupted": result.get("files_corrupted", 0),
            "manifest_path": result.get("manifest_path", ""),
            "metadata_path": result.get("metadata_path", ""),
            "summary": result.get("summary", {})
        }
    except Exception as e:
        log.exception(f"Errore ingestion: {e}")
        return {
            "success": False,
            "message": f"Errore durante ingestion: {str(e)}"
        }

@app.post("/upload/", tags=["admin"])
def upload_files(request: Request, files: list[UploadFile] = File(...), payload: dict = Depends(validate_token)):
    saved_files = []
    params = request.app.state.params
    data_dir = params["data_dir"]
    if request.app.state.reindexing:
        return {
            "reindex": True,
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

@app.post("/test", tags=["admin"])
async def test(request: Request, body: ChatRequest = Body(...)):
    risultati = []

    for domanda in test_domande:
        nuovo_body = ChatRequest(
            prompt=domanda,
            top_k=body.top_k if body.top_k > 0 else None,
            distance_threshold=body.distance_threshold if body.distance_threshold >0 else None
        )

        response = await chat(request, nuovo_body)
        risultati.append({
            "domanda": domanda,
            "risposta": response.answer,
            "sources": response.sources
        })

    return {"test_results": risultati}


if __name__ == "__main__":
    import uvicorn

    run_migrations()  # Esegue creazione DB

    """solo una volta per inserire i parametri altrimenti manualmente
    parameter_db = ParameterDB()
    parameter_db.set("llm_model", "mistral", descrizione="Modello LLM da utilizzare")
    parameter_db.set("embed_model", "intfloat/e5-large-v2", descrizione="Modello di embedding da utilizzare")
    parameter_db.set("chunk_size", 1500, tipo="number", descrizione="Dimensione chunk documenti")
    parameter_db.set("chunk_overlap", 200, tipo="number",descrizione="Overlap chunk")
    parameter_db.set("top_k", 8, tipo="number", descrizione="Top K chunk")
    parameter_db.set("distance_threshold", 0.6, tipo="decimale",descrizione="Soglia di similarità")
    parameter_db.set("EXCLUDED_EXTS",".md, .csv, .png, .jpg, .jpeg", tipo="tupla",descrizione="Cartella documenti")
    parameter_db.set("DATA_DIR","Documenti", tipo="string",descrizione="Cartella documenti")
    parameter_db.set("DIRETTIVA_PROMPT",DIRETTIVA_PROMPT, tipo="string",descrizione="Direttiva di prompt per il modello")
    parameter_db.set("Models","phi3:medium,mistral:latest, qwen3-vi:8b, qwen3-vi:4b, qwen3:30b, qwen3:8b, qwen3:4b, gemma:2b", tipo="list",descrizione="Modelli LLM disponibili")
    """


    log.info("Avvio server uvicorn su 0.0.0.0:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
