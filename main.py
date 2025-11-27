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
from fastapi import FastAPI, Body, HTTPException, Request, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from auth import hash_password, verify_password, create_jwt, validate_token
from database.connection import DBConnection
from database.migration import run_migrations
from logger_ragis.rag_log import RagLog
from rag.embeddings import get_vector_db
from rag.indexing import build_vector_db
from rag.rag_query import decide_from_db, query_rag
from settings import *

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
    # Esegui le migrazioni e assicurati che l'utente di default esista
    # Questo permette di avere l'utente 'admin' con password 'admin'
    await asyncio.to_thread(run_migrations)

    params = resolve_params()
    # Salvi il job nella app state
    cron_reindex = params["cron_reindex"]
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

    params = resolve_params()
    top_k = body.top_k if body.top_k is not None else params["top_k"]
    distance_threshold = (
        body.distance_threshold
        if body.distance_threshold is not None
        else params["distance_threshold"]
    )

    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt vuoto")

    match, msg = decide_from_db(body.prompt, threshold=body.distance_threshold or distance_threshold,
                                top_k=body.top_k or top_k)
    answer_init=""
    if not match:
        answer_init = "Non ho trovato informazioni rilevanti nei documenti."

    try:
        answer, sources = query_rag(body.prompt, top_k=body.top_k or top_k,
                                    distance_threshold=body.distance_threshold or distance_threshold)
        if not answer:
            return ChatResponse(
                answer="Non ho abbastanza informazioni nei documenti per rispondere. Specifica contesto o carica documenti.",
                sources=sources)

        return ChatResponse(answer=f"{answer_init} {answer}", sources=sources)
    except Exception as e:
        log.exception("Errore query_rag")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/reindex/", tags=["admin"])
def reindex(payload: dict = Depends(validate_token)):
    try:
        result = build_vector_db()
        return {"message": result.get("message", "OK")}
    except Exception as e:
        log.exception("Errore indicizzazione")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/debug_db/", )
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

@app.get("/get_parameters", tags=["admin"])
def get_parameters(payload: dict = Depends(validate_token)):
    return resolve_params()


@app.post("/save_parameters", tags=["admin"])
def save_parameters(body, payload: dict = Depends(validate_token)):
    try:
        parameter_db = ParameterDB()
        for key, value in body.items():
            parameter_db.set(key, value)
        return {"message": "Parametri salvati con successo"}
    except Exception as e:
        log.exception("Errore salvataggio parametri")
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/get_models",tags=["admin"])
def get_models(payload: dict = Depends(validate_token)):
    try:
        parameter=resolve_params()
        models=parameter["Models"]
        return {"models": models}
    except Exception as e:
        log.exception("Errore recupero modelli")
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/login")
def login(body: LoginRequest):
    conn = DBConnection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE username = ?", (body.username,))
    row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="Credenziali non valide")

    stored_hash = row["password_hash"]

    if not verify_password(body.password, stored_hash):
        raise HTTPException(status_code=401, detail="Credenziali non valide")

    ruolo = row["ruolo"]

    token = create_jwt(body.username, ruolo)

    return {
        "token": token,
        "username": body.username,
        "ruolo": ruolo
    }


@app.post("/registrazione", tags=["admin"])
def register(body: UserRequest, payload: dict = Depends(validate_token)):
    # Solo admin può creare nuovi utenti
    ruolo_richiedente = payload.get("ruolo", "").lower()
    if ruolo_richiedente != "admin":
        raise HTTPException(status_code=403, detail="Solo admin può creare utenti")

    conn = DBConnection()
    cur = conn.cursor()

    hashed = hash_password(body.password)

    log.info(f"Tentativo di registrazione: username={body.username}, ruolo={body.ruolo}")

    try:
        cur.execute("""
            INSERT INTO users (username, password_hash, ruolo)
            VALUES (?, ?, ?)
        """, (body.username, hashed, body.ruolo))

        conn.conn.commit()
        log.info(f"Utente {body.username} creato con successo")

    except Exception as e:
        log.exception(f"Errore nella creazione utente {body.username}: {e}")
        raise HTTPException(status_code=400, detail="Username già esistente")

    return {"messaggio": "Registrazione completata"}


@app.get("/lista-utenti", tags=["admin"])
def lista_utenti(payload: dict = Depends(validate_token)):
    # Solo admin può leggere la lista utenti
    ruolo_richiedente = payload.get("ruolo", "").lower()
    if ruolo_richiedente != "admin":
        raise HTTPException(status_code=403, detail="Solo admin può accedere alla lista utenti")

    conn = DBConnection()
    cur = conn.cursor()

    try:
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


@app.put("/aggiorna-utente/{user_id}", tags=["admin"])
def aggiorna_utente(user_id: int, body: UserRequest, payload: dict = Depends(validate_token)):
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

    try:
        cur.execute(query, tuple(values))
        conn.conn.commit()

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Utente non trovato")

        return {"messaggio": "Utente aggiornato correttamente"}

    except Exception as e:
        log.exception(f"Errore aggiornamento utente {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Errore durante aggiornamento")


@app.delete("/cancella-utente/{user_id}", tags=["admin"])
def cancella_utente(user_id: int, payload: dict = Depends(validate_token)):
    # Solo admin
    ruolo_richiedente = payload.get("ruolo", "").lower()
    if ruolo_richiedente != "admin":
        raise HTTPException(status_code=403, detail="Solo admin può cancellare utenti")

    conn = DBConnection()
    cur = conn.cursor()

    try:
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.conn.commit()

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Utente non trovato")

        return {"messaggio": "Utente cancellato con successo"}

    except Exception as e:
        log.exception(f"Errore cancellazione utente {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Errore durante cancellazione utente")


@app.post("/upload/", tags=["admin"])
def upload_files(request: Request, files: list[UploadFile] = File(...), payload: dict = Depends(validate_token)):
    saved_files = []
    params = resolve_params()
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
    parameter_db.set("Models","mistral, qwen3-vi:8b, qwen3-vi:4b, qwen3:30b, qwen3:8b, qwen3:4b, gemma:2b", tipo="list",descrizione="Modelli LLM disponibili")
    """

    log.info("Avvio server uvicorn su 0.0.0.0:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
