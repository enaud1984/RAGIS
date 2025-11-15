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
from logger_ragis.rag_log import RagLog

from fastapi import FastAPI, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware


from parameter import *
from rag.embeddings import get_vector_db
from rag.indexing import build_vector_db
from rag.rag_query import decide_from_db, query_rag

log = RagLog.get_logger("Ragis")


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
