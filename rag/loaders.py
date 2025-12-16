import glob
import hashlib
import json
from pathlib import Path
from typing import List

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredEmailLoader,
    UnstructuredExcelLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredFileLoader
)
from starlette.requests import Request

from settings import *
from logger_ragis.rag_log import RagLog


log = RagLog.get_logger("loaders")


def load_manifest_entries(manifest_path: Path) -> dict:
    """Carica manifest.jsonl in memoria per ricerca veloce.
    
    Ritorna: {ingested_path: entry_dict}
    """
    manifest = {}
    if not manifest_path.exists():
        return manifest
    
    try:
        with open(manifest_path, encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    ingested_path = entry.get("ingested_path")
                    if ingested_path:
                        manifest[ingested_path] = entry
                except json.JSONDecodeError:
                    pass
        log.debug(f"Manifest caricato: {len(manifest)} entries")
    except Exception as e:
        log.warning(f"Errore caricando manifest: {e}")
    
    return manifest

def load_all_documents(request: Request, base_dir: Path) -> List:
    """Carica tutti i documenti utili alla indicizzazione.
    
    Strategia:
    1. Se Documenti_ingested/ esiste → preferisci quello (normalizzato + tracciabile)
       - Carica SOLO da by_format/ (sorgente di verità)
       - Ignora by_date/ (sono symlink/copy ridondanti)
    2. Altrimenti fallback a Documenti/ (backward compatibility)
    """
    docs = []
    params = request.app.state.params
    excluded_exts = params["excluded_exts"]
    
    # Rileva se usare ingested directory
    ingested_dir = base_dir.parent / "Documenti_ingested"
    use_ingested = ingested_dir.exists()
    
    if use_ingested:
        log.info("Usando Documenti_ingested/ (normalizzato)")
        manifest_path = ingested_dir / "manifest.jsonl"
        manifest = load_manifest_entries(manifest_path)
        
        # Carica SOLO da by_format/ (la sorgente unica di verità)
        by_format_dir = ingested_dir / "by_format"
        if not by_format_dir.exists():
            log.warning("by_format/ non trovato in Documenti_ingested/")
            return docs
        
        # Ricerca ricorsiva in by_format/
        for path_str in glob.glob(str(by_format_dir / "**" / "*.*"), recursive=True):
            path = Path(path_str)
            
            if path.suffix.lower() in excluded_exts:
                continue
            
            try:
                log.debug(f"Caricando: {path.relative_to(ingested_dir)}")
                loader = smart_loader(path)
                subdocs = loader.load()
                
                # Arricchisci metadati da manifest
                for d in subdocs:
                    d.metadata["source"] = str(path)
                    
                    # Rileva percorso relativo da ingested_dir (by_format/pdf/...)
                    rel_path = path.relative_to(ingested_dir)
                    rel_path_str = str(rel_path).replace("\\", "/")
                    
                    # Cerca nel manifest
                    if rel_path_str in manifest:
                        entry = manifest[rel_path_str]
                        d.metadata["original_path"] = entry.get("original_path", "")
                        d.metadata["file_hash"] = entry.get("file_hash", "")
                        d.metadata["content_sha256"] = entry.get("content_sha256", "")
                        d.metadata["ingestion_timestamp"] = entry.get("ingestion_timestamp", "")
                        d.metadata["encoding"] = entry.get("encoding", "utf-8")
                    else:
                        log.debug(f"Manifest entry non trovato per {rel_path_str}")
                
                docs.extend(subdocs)
                log.info("Caricato %s (%d parti)", path.name, len(subdocs))
            except Exception as e:
                log.error("Errore caricando %s: %s", path, e)
    else:
        # Fallback a Documenti/ raw
        log.info("Fallback a Documenti/ (nessun ingested trovato)")
        source_dir = base_dir
        
        for path_str in glob.glob(str(source_dir / "**" / "*.*"), recursive=True):
            path = Path(path_str)
            
            if path.suffix.lower() in excluded_exts:
                continue
            
            try:
                log.debug(f"Caricando: {path.relative_to(source_dir)}")
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
