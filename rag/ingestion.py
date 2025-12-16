"""
INGESTION LAYER - Fase deterministica di normalizzazione documenti

Responsabilità:
- Legge documenti grezzi da Documenti/
- Valida, normalizza, organizza in Documenti_ingested/
- Preserva metadati (source, timestamp, hash, encoding)
- ZERO trasformazioni semantiche (no chunking, embedding, inference)
- Output deterministico e riproducibile

Design principle: "Boring is good" - semplicità, robustezza, tracciabilità.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import chardet

from logger_ragis.rag_log import RagLog

log = RagLog.get_logger("ingestion")


# ============================================================================
# CONFIGURAZIONE DEFAULTS
# ============================================================================

DEFAULT_CONFIG = {
    "supported_formats": [".txt", ".pdf", ".docx", ".xlsx", ".eml", ".md", ".html"],
    "max_file_size_bytes": 1 * 1024 * 1024 * 1024,  # 1GB - sanity check
    "max_filename_length": 128,
    "encoding_fallback_chain": ["utf-8", "iso-8859-1", "cp1252", "latin-1"],
    "skip_hidden": True,  # Salta file che iniziano con .
}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def compute_file_hash(file_path: Path, algorithm: str = "sha256") -> Tuple[str, str]:
    """
    Computa hash deterministico del file.
    
    Returns:
        (short_hash[:16], full_hash) per deduplicazione e integrità
    """
    hasher = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    full_hash = hasher.hexdigest()
    return full_hash[:16], full_hash


def detect_encoding(file_path: Path) -> Optional[str]:
    """
    Riconosce encoding di un file di testo.
    
    Logica:
    1. Prova a riconoscere con chardet (probabilistico)
    2. Se fallisce, ritorna None (il caller userrà fallback chain)
    
    Why chardet: Non assume UTF-8, riconosce anche ISO-8859-1, CP1252, ecc.
    Trade-off: Probabilistico, non 100% accurato, ma meglio di fallback cieco.
    """
    try:
        with open(file_path, "rb") as f:
            raw_data = f.read(10000)  # Leggi primo 10KB per velocità
        detected = chardet.detect(raw_data)
        if detected and detected.get("encoding"):
            return detected["encoding"]
    except Exception as e:
        log.warning(f"Chardet fallito per {file_path.name}: {e}")
    return None


def sanitize_filename(original_name: str, max_length: int = 128) -> str:
    """
    Normalizza nome file per filesystems Windows/Linux.
    
    Logica:
    - Sostituisci spazi e separatori con underscore
    - Rimuovi caratteri illegali: < > : " / \ | ? *
    - Lowercase (per consistency cross-platform)
    - Limita lunghezza
    
    Esempio: "Contratto Vendita 2025.pdf" → "contratto_vendita_2025.pdf"
    """
    # Sostituisci spazi/dash con underscore
    sanitized = original_name.replace(" ", "_").replace("-", "_")
    
    # Rimuovi caratteri illegali (Windows + Unix)
    illegal_chars = '<>:"/\\|?*'
    for char in illegal_chars:
        sanitized = sanitized.replace(char, "")
    
    # Lowercase
    sanitized = sanitized.lower()
    
    # Limita lunghezza (account per hash prefix: "16chars_")
    if len(sanitized) > max_length:
        # Preserva estensione
        name_part, ext = sanitized.rsplit(".", 1) if "." in sanitized else (sanitized, "")
        name_part = name_part[:max_length - len(ext) - 1]
        sanitized = f"{name_part}.{ext}" if ext else name_part
    
    return sanitized


def get_file_format(file_path: Path) -> Optional[str]:
    """Ritorna formato file (estensione minuscola con punto)."""
    suffix = file_path.suffix.lower()
    return suffix if suffix else None


def validate_file(
    file_path: Path,
    config: dict,
) -> Tuple[bool, Optional[str]]:
    """
    Valida un file per l'ingestion.
    
    Returns:
        (is_valid, error_message)
    
    Checks:
    1. File esiste e è file (non directory)
    2. Non è hidden (inizia con .)
    3. Estensione supportata
    4. Size > 0
    5. Size < max_size
    """
    # 1. Esiste?
    if not file_path.exists():
        return False, f"File non esiste: {file_path}"
    if not file_path.is_file():
        return False, f"Non è un file: {file_path}"
    
    # 2. Hidden?
    if config["skip_hidden"] and file_path.name.startswith("."):
        return False, "File hidden"
    
    # 3. Estensione supportata?
    file_format = get_file_format(file_path)
    if file_format not in config["supported_formats"]:
        return False, f"Formato non supportato: {file_format}"
    
    # 4. Empty?
    file_size = file_path.stat().st_size
    if file_size == 0:
        return False, "File vuoto (0 bytes)"
    
    # 5. Too large?
    if file_size > config["max_file_size_bytes"]:
        return False, f"File troppo grande ({file_size} bytes > {config['max_file_size_bytes']})"
    
    return True, None


def attempt_read_text(
    file_path: Path,
    encoding_fallback_chain: List[str],
) -> Tuple[Optional[str], Optional[str]]:
    """
    Tenta di leggere file di testo con fallback su encoding diversi.
    
    Logica:
    1. Rileva encoding con chardet
    2. Prova detect encoding + fallback chain
    3. Se tutto fallisce, ritorna (None, error_msg)
    
    Returns:
        (content, detected_encoding) o (None, error_message)
    
    Why tiered approach: Alcuni file sono ambigui (ISO-8859-1 vs UTF-8).
    Fallback chain evita di scartare documenti per encoding unknown.
    """
    detected_enc = detect_encoding(file_path)
    encodings_to_try = [detected_enc] if detected_enc else []
    encodings_to_try.extend(encoding_fallback_chain)
    
    for enc in encodings_to_try:
        if not enc:
            continue
        try:
            with open(file_path, "r", encoding=enc) as f:
                content = f.read()
            log.debug(f"Leggi {file_path.name} con encoding {enc}")
            return content, enc
        except (UnicodeDecodeError, LookupError):
            continue
    
    return None, f"Nessun encoding funzionò: {encodings_to_try}"


# ============================================================================
# INGESTION CORE LOGIC
# ============================================================================

def ingest_documents(
    source_dir: str | Path = "Documenti",
    ingested_dir: str | Path = "Documenti_ingested",
    config: dict = None,
    deterministic: bool = True,
) -> dict:
    """
    Ingestion pipeline deterministica.
    
    Args:
        source_dir: Cartella input (default: "Documenti/")
        ingested_dir: Cartella output (default: "Documenti_ingested/")
        config: Dict con opzioni (vedi DEFAULT_CONFIG)
        deterministic: Se True, usa timestamp fisso per reproducibilità
    
    Returns:
        dict {
            "success": bool,
            "total_files_found": int,
            "files_ingested": int,
            "files_skipped": int,
            "files_corrupted": int,
            "manifest_path": str,
            "metadata_path": str,
            "summary": {
                "by_format": {...},
                "total_size_mb": float,
            },
            "skipped_files": [...],
            "warnings": [...]
        }
    
    Comportamento:
    - Ricerca ricorsivamente in source_dir
    - Per ogni file valido: copia in ingested_dir con naming standardizzato
    - Genera manifest.jsonl (1 linea JSON per file)
    - Genera metadata.json (indice globale + config usata)
    - Determinisico: stessi input → stessi output (incluso timestamp se flag=True)
    """
    
    # Setup
    source_dir = Path(source_dir).resolve()
    ingested_dir = Path(ingested_dir).resolve()
    config = {**DEFAULT_CONFIG, **(config or {})}
    
    if not source_dir.exists():
        return {
            "success": False,
            "error": f"Source dir non esiste: {source_dir}",
            "total_files_found": 0,
            "files_ingested": 0,
            "files_skipped": 0,
            "files_corrupted": 0,
        }
    
    # Crea cartelle output
    ingested_dir.mkdir(parents=True, exist_ok=True)
    (ingested_dir / "by_format").mkdir(exist_ok=True)
    (ingested_dir / "by_date").mkdir(exist_ok=True)
    
    # Timestamp fisso per determinismo
    ingest_ts = datetime.now(timezone.utc)
    if deterministic:
        # Per reproducibilità, fissa l'ora a midnight UTC
        ingest_ts = ingest_ts.replace(hour=0, minute=0, second=0, microsecond=0)
    ingest_ts_iso = ingest_ts.isoformat() + "Z"
    ingest_date = ingest_ts.strftime("%Y-%m-%d")
    
    # Tracking
    manifest_entries = []
    seen_hashes = set()
    stats = {
        "total_files_found": 0,
        "files_ingested": 0,
        "files_skipped": 0,
        "files_corrupted": 0,
        "by_format": {},
        "total_size_bytes": 0,
    }
    skipped_files = []
    warnings = []
    
    log.info(f"Inizio ingestion: {source_dir} → {ingested_dir}")
    
    # ===== PROCESSING LOOP =====
    # Ricerca ricorsiva file
    for source_file in sorted(source_dir.rglob("*")):
        if not source_file.is_file():
            continue
        
        stats["total_files_found"] += 1
        relative_path = source_file.relative_to(source_dir)
        
        # Validazione
        is_valid, error_msg = validate_file(source_file, config)
        if not is_valid:
            log.debug(f"SKIP {relative_path}: {error_msg}")
            stats["files_skipped"] += 1
            skipped_files.append({
                "original_path": str(relative_path),
                "reason": error_msg,
            })
            continue
        
        try:
            # Calcola hash per deduplicazione
            short_hash, full_hash = compute_file_hash(source_file)
            
            # Check duplicati (stesso contenuto)
            if short_hash in seen_hashes:
                log.info(f"DEDUP {relative_path} (hash already seen)")
                stats["files_skipped"] += 1
                skipped_files.append({
                    "original_path": str(relative_path),
                    "reason": "Duplicato (hash già visto)",
                })
                continue
            
            seen_hashes.add(short_hash)
            
            # Determina formato
            file_format = get_file_format(source_file)
            format_dir = ingested_dir / "by_format" / file_format.lstrip(".")
            format_dir.mkdir(parents=True, exist_ok=True)
            
            # Naming standardizzato
            sanitized_name = sanitize_filename(source_file.stem)
            dest_filename = f"{short_hash}_{sanitized_name}{file_format}"
            dest_path = format_dir / dest_filename
            
            # Copia file (operazione idempotente)
            if not dest_path.exists():
                import shutil
                shutil.copy2(source_file, dest_path)
                log.debug(f"COPY {relative_path} → {dest_path.relative_to(ingested_dir)}")
            else:
                log.debug(f"EXIST {dest_path.relative_to(ingested_dir)}")
            
            # Simbolic link in by_date/
            date_dir = ingested_dir / "by_date" / ingest_date
            date_dir.mkdir(parents=True, exist_ok=True)
            date_link = date_dir / dest_filename
            if not date_link.exists():
                # Symlink relativo per portabilità
                # Calcola percorso relativo da by_date/YYYY-MM-DD a by_format/ext/
                try:
                    # Percorso relativo dalla destinazione al target
                    format_subdir = file_format.lstrip(".")
                    rel_target = Path("..") / ".." / "by_format" / format_subdir / dest_filename
                    date_link.symlink_to(rel_target)
                except (OSError, NotImplementedError):
                    # Windows/unsupported: fallback copia
                    import shutil
                    shutil.copy2(dest_path, date_link)
            
            # Rileva encoding (solo per text files)
            detected_encoding = None
            if file_format in [".txt", ".md", ".html", ".eml"]:
                detected_encoding = detect_encoding(source_file)
            
            # Metadata entry
            entry = {
                "original_path": str(relative_path),
                "ingested_path": str(dest_path.relative_to(ingested_dir)),
                "format": file_format.lstrip("."),
                "file_hash": short_hash,
                "content_sha256": full_hash,
                "file_size": source_file.stat().st_size,
                "encoding": detected_encoding,
                "ingestion_timestamp": ingest_ts_iso,
                "status": "valid",
                "validation_notes": "",
            }
            
            manifest_entries.append(entry)
            
            # Aggiorna stats
            stats["files_ingested"] += 1
            format_key = file_format.lstrip(".")
            stats["by_format"][format_key] = stats["by_format"].get(format_key, 0) + 1
            stats["total_size_bytes"] += entry["file_size"]
            
            log.info(f"INGEST ✓ {relative_path}")
            
        except Exception as e:
            log.exception(f"CORRUPT {relative_path}: {e}")
            stats["files_corrupted"] += 1
            skipped_files.append({
                "original_path": str(relative_path),
                "reason": f"Errore processing: {str(e)[:100]}",
            })
    
    # ===== WRITE MANIFEST & METADATA =====
    manifest_path = ingested_dir / "manifest.jsonl"
    with open(manifest_path, "w", encoding="utf-8") as f:
        for entry in manifest_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    log.info(f"Manifest scritto: {manifest_path}")
    
    metadata = {
        "ingestion_timestamp": ingest_ts_iso,
        "source_dir": str(source_dir),
        "ingested_dir": str(ingested_dir),
        "deterministic": deterministic,
        "config_used": config,
        "stats": stats,
        "manifest_path": str(manifest_path),
    }
    metadata_path = ingested_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    log.info(f"Metadata scritto: {metadata_path}")
    
    # ===== RETURN RESULT =====
    return {
        "success": True,
        "total_files_found": stats["total_files_found"],
        "files_ingested": stats["files_ingested"],
        "files_skipped": stats["files_skipped"],
        "files_corrupted": stats["files_corrupted"],
        "manifest_path": str(manifest_path),
        "metadata_path": str(metadata_path),
        "summary": {
            "by_format": stats["by_format"],
            "total_size_mb": round(stats["total_size_bytes"] / (1024 * 1024), 2),
        },
        "skipped_files": skipped_files,
        "warnings": warnings,
    }


# ============================================================================
# CLI ENTRY POINT (opzionale, per testing)
# ============================================================================

if __name__ == "__main__":
    import sys
    
    source = sys.argv[1] if len(sys.argv) > 1 else "Documenti"
    ingested = sys.argv[2] if len(sys.argv) > 2 else "Documenti_ingested"
    
    result = ingest_documents(source, ingested, deterministic=True)
    
    print("\n" + "=" * 80)
    print(f"Ingestion Results ({result['ingestion_timestamp']})")
    print("=" * 80)
    print(f"Total files found: {result['total_files_found']}")
    print(f"  ✓ Ingested: {result['files_ingested']}")
    print(f"  ⊘ Skipped: {result['files_skipped']}")
    print(f"  ✗ Corrupted: {result['files_corrupted']}")
    print(f"\nBy format: {result['summary']['by_format']}")
    print(f"Total size: {result['summary']['total_size_mb']} MB")
    print(f"\nManifest: {result['manifest_path']}")
    print(f"Metadata: {result['metadata_path']}")
    if result["skipped_files"]:
        print(f"\nSkipped ({len(result['skipped_files'])}):")
        for s in result["skipped_files"][:5]:
            print(f"  - {s['original_path']}: {s['reason']}")
        if len(result["skipped_files"]) > 5:
            print(f"  ... e {len(result['skipped_files']) - 5} altri")
    print("=" * 80)
