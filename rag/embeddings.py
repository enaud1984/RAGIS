from logger_ragis.rag_log import RagLog
from functools import lru_cache
from settings import *
from langchain_chroma import Chroma
from langchain.embeddings import HuggingFaceEmbeddings

log = RagLog.get_logger("embedding")
# --------- Singleton factories for embeddings & vectordb ----------
@lru_cache(maxsize=10)
def load_embedding_model(model_name: str):
    """Carica un modello HuggingFace e lo cache-a per nome."""
    log.info(f"Inizializzo embedding model: {model_name}")
    return HuggingFaceEmbeddings(model_name=model_name)

def get_embeddings():
    params = request.app_.state.params
    model_name = params["embed_model"]
    return load_embedding_model(model_name)

@lru_cache(maxsize=1)
def get_vector_db():
    """Crea e ritorna un'istanza Chroma singleton.
    Nota: Chroma puede caricare da persist_directory.
    """
    log.info("Apro/creo Chroma DB in: %s", DB_DIR)
    embeddings = get_embeddings()
    return Chroma(persist_directory=str(DB_DIR), embedding_function=embeddings)

