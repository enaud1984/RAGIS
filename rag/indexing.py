from typing import Dict

from langchain_text_splitters import RecursiveCharacterTextSplitter

from logger_ragis.rag_log import RagLog
from parameter import *
from rag.embeddings import get_vector_db
from rag.loaders import load_all_documents, get_file_hash

log = RagLog.get_logger("indexing")
# --------- Indicizzazione incrementale ----------
def build_vector_db() -> Dict[str, str]:
    log.info("Start indicizzazione incrementale...")
    vectordb = get_vector_db()

    # recupera metadati esistenti per dedup basata su hash
    try:
        existing = vectordb.get()
    except Exception as e:
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
        vectordb.persist()
    except Exception as e:
        log.warning(f"Persist automatico non disponibile; forse non necessario. {e}")


    msg = f"Indicizzati {len(new_docs)} nuovi documenti (tot chunk: {len(chunks)})."
    log.info(msg)
    return {"message": msg}

