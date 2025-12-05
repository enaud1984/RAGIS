import glob
import hashlib


from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredEmailLoader,
    UnstructuredExcelLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredFileLoader
)

from settings import *
from logger_ragis.rag_log import RagLog


log = RagLog.get_logger("loaders")

def load_all_documents(base_dir: Path) -> List:
    """Carica tutti i documenti utili alla indicizzazione."""
    docs = []
    params = resolve_params()
    excluded_exts = params["excluded_exts"]
    for path_str in glob.glob(str(base_dir / "**" / "*.*"), recursive=True):
        path = Path(path_str)
        if path.suffix.lower() in excluded_exts:
            continue
        try:
            log.info(f"Caricando documento: {path}")
            loader = smart_loader(path)
            subdocs = loader.load()
            for d in subdocs:
                d.metadata["source"] = str(path)
            docs.extend(subdocs)
            log.info("Caricato %s (%d parti)", path.name, len(subdocs))
        except Exception as e:
            log.error("Errore caricando %s: %s", path, e)
    log.info("Totale documenti caricati: %d", len(docs))
    return docs

def smart_loader(path: Path):
    ext = path.suffix.lower()
    if ext == ".pdf":
        return PyPDFLoader(str(path))
    if ext in (".doc", ".docx"):
        return UnstructuredWordDocumentLoader(str(path))
    if ext == ".txt":
        return TextLoader(str(path), encoding="utf-8")
    if ext == ".eml":
        return UnstructuredEmailLoader(str(path))
    if ext in (".xls", ".xlsx"):
        return UnstructuredExcelLoader(str(path))
    # fallback
    return UnstructuredFileLoader(str(path))

def get_file_hash(path: Path) -> str:
    """MD5 file hash (usato per dedup)."""
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
