

from logger_ragis.rag_log import RagLog
from functools import lru_cache
from parameter import *
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

log = RagLog.get_logger("embedding")
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

