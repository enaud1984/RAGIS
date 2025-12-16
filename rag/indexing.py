from typing import Dict

from langchain_text_splitters import RecursiveCharacterTextSplitter
from starlette.requests import Request

from logger_ragis.rag_log import RagLog

from settings import *
from rag.embeddings import get_vector_db
from rag.loaders import load_all_documents, get_file_hash
from rag.dynamic_chunking import create_db_with_dynamic_chunking, ChunkingConfig

log = RagLog.get_logger("indexing")
# --------- Indicizzazione incrementale ----------
def build_vector_db(request: Request, use_dynamic_chunking: bool = True) -> Dict[str, str]:
    log.info("Start indicizzazione incrementale...")
    params = request.app.state.params
    excluded_exts = params["excluded_exts"]
    vectordb = get_vector_db(request)
    data_dir = params["data_dir"]
    chunk_overlap=params["chunk_overlap"]
    chunk_size=params["chunk_size"]

    # recupera metadati esistenti per dedup basata su hash
    try:
        existing = vectordb.get()
    except Exception as e:
        existing = {}
    existing_hashes = set(m.get("hash") for m in existing.get("metadatas", []) if m.get("hash"))

    all_docs = load_all_documents(request, data_dir)
    valid_docs = [d for d in all_docs if not d.metadata.get("source", "").lower().endswith(excluded_exts)]
    
    # Log provenienza documenti
    has_original_path = sum(1 for d in valid_docs if d.metadata.get("original_path"))
    if has_original_path > 0:
        log.info(f"PROVENIENZA: {has_original_path}/{len(valid_docs)} documenti da Documenti_ingested/ (tracciabili)")
    else:
        log.info(f"PROVENIENZA: Documenti caricati da Documenti/ (nessun ingestion)")
    
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
    
    log.info("INDICIZZAZIONE CON %d DOCUMENTI NUOVI (strategia: %s)",
             len(new_docs),
             "DYNAMIC" if use_dynamic_chunking else "STATIC")
    
    # ===== SCELTA DELLA STRATEGIA DI CHUNKING =====
    if use_dynamic_chunking:
        chunks = create_db_with_dynamic_chunking(
            new_docs,
            config=ChunkingConfig(
                min_chunk_tokens=100,
                max_chunk_tokens=600,
                respect_structure=True,
                merge_small_chunks=True
            )
        )
        log.info("Chunking dinamico completato: %d chunk generati", len(chunks))
    else:
        # Fallback statico (vecchio metodo)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        chunks = splitter.split_documents(new_docs)
        log.info("Chunking statico (ricorsivo) completato: %d chunk", len(chunks))

    ids = []
    for i, c in enumerate(chunks):
        root_hash = c.metadata.get("hash", "nohash")
        c.metadata["chunk_index"] = i
        ids.append(f"{root_hash}-{i}")
    if not chunks:
        return {"message": "Nessun chunk da indicizzare, documento ignorato."}

    vectordb.add_documents(documents=chunks, ids=ids)

    # Persistenza corretta per la nuova API
    try:
        vectordb.persist()
    except Exception as e:
        log.warning(f"Persist automatico non disponibile; forse non necessario. {e}")

    msg = (
        f"✓ Indicizzati {len(new_docs)} nuovi documenti "
        f"→ {len(chunks)} chunk "
        f"[{'DYNAMIC' if use_dynamic_chunking else 'STATIC'}]"
    )
    log.info(msg)
    return {"message": msg}

