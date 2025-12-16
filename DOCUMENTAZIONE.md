# 📚 RAGIS - Documentazione Completa (Aggiornata v1.2)

## 📖 Indice
1. [Panoramica Generale](#panoramica-generale)
2. [Architettura del Sistema](#architettura-del-sistema)
3. [Flusso Tecnico](#flusso-tecnico)
4. [Moduli Principali](#moduli-principali)
   - 4.bis [Ingestion Layer (NEW v1.2)](#4bis-ragingestrationpy---normalizzazione-documenti-new-v12)
5. [API Endpoints](#api-endpoints)
6. [Database](#database)
7. [Autenticazione e Autorizzazione](#autenticazione-e-autorizzazione)
8. [Configurazione](#configurazione)
9. [Chunking Dinamico](#chunking-dinamico)
10. [Guida All'Uso](#guida-alluso)

---

## 🎯 Panoramica Generale

**RAGIS v1.2** è un sistema **Retrieval-Augmented Generation (RAG)** per studi legali italiani con **ingestion layer** completo e **chunking dinamico** per miglior qualità dei risultati. Permette di:

- 📥 **Ingestionare documenti** (NEW v1.2): Normalizzazione, validazione, deduplicazione content-based
- 📤 **Caricare documenti** (PDF, Word, Email, Excel, TXT)
- 🔍 **Indicizzare** con chunking dinamico (rispetta struttura documenti)
- 💬 **Interrogare** con risposte standard e streaming
- 👥 **Gestire utenti** con differenti ruoli (admin, user)
- ⚙️ **Configurare parametri** e modelli LLM dinamicamente
- 🔐 **Autenticare** tramite JWT (12 ore TTL)
- 🤖 **Gestire modelli Ollama** (download, selezione, stato)
- 📊 **Tracciare provenance** (NEW v1.2): Ogni risposta tracciabile fino al documento originale

**Stack tecnologico:**
- Backend: FastAPI (Python 3.10+)
- Ingestion: chardet (encoding detection), hashlib (SHA256), pathlib, json, logging
- LLM: Ollama (modelli locali: Mistral, Llama, Qwen, Phi, Gemma)
- Embeddings: HuggingFace (intfloat/e5-large-v2)
- VectorDB: Chroma (persistente, HNSW indexing)
- Database: SQLite
- Chunking: DynamicChunker (strutturale + semantico 4-level)
- Frontend: React.js

---

## 🏗️ Architettura del Sistema (v1.2 - Con Ingestion Layer)

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                      │
│                   rag-interface/src/                     │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP/REST
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   BACKEND (FastAPI)                      │
│                     main.py                              │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Endpoints (UPDATED v1.2):                         │ │
│  │  • POST /ingest/ → Ingestion layer (NEW)           │ │
│  │  • POST /chat/ → Query RAG                         │ │
│  │  • POST /chat/stream → Query RAG streaming         │ │
│  │  • POST /upload/ → Upload documenti                │ │
│  │  • GET /reindex/ → Reindex (ingestion+chunking)   │ │
│  │  • POST /login → Autenticazione                    │ │
│  │  • POST /registrazione → Registra utente           │ │
│  │  • GET /lista-utenti → Lista utenti (admin)        │ │
│  │  • PUT /aggiorna-utente → Modifica utente          │ │
│  │  • DELETE /cancella-utente → Cancella utente       │ │
│  │  • GET /debug_db/ → Debug vettoriale               │ │
│  │  • GET /get_models → Lista modelli Ollama          │ │
│  │  • POST /download_model → Scarica modello          │ │
│  │  • GET /get_parameters → Parametri di sistema      │ │
│  │  • POST /save_parameters → Salva parametri         │ │
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
    │          │            │                    │
    ▼          ▼            ▼                    ▼
┌────────┐ ┌────────────┐ ┌──────────────┐ ┌──────────┐
│Ingestion│ │ Auth       │ │ RAG          │ │ Database │
│ (NEW)   │ │ (auth.py)  │ │ Processing   │ │(db_sql/) │
│         │ │            │ │ (rag/)       │ │          │
│• Norm.  │ │ • JWT      │ │• embeddings  │ │• SQLite  │
│• Valid. │ │ • BCrypt   │ │• indexing    │ │• Users   │
│• Dedup  │ │ • Hash     │ │• loaders     │ │• Params  │
│• Org.   │ │            │ │• rag_query   │ │          │
└────────┘ └────────────┘ └──────────────┘ └──────────┘
    │                             │
    │ Output:                     │
    │ Documenti_ingested/         │
    │ + manifest.jsonl            │
    │ + metadata.json             │
    │                             │
    └─────────────────┬───────────┘
                      ▼
            ┌─────────────────────┐
            │ load_all_documents()│
            │ (loaders.py - UPDA) │
            │                     │
            │ • Prefer ingested/  │
            │ • Load manifest     │
            │ • Enrich metadata   │
            │ • Fallback to raw/  │
            └──────────┬──────────┘
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
    ┌──────────────────┐  ┌──────────────┐
    │ DynamicChunker   │  │ Chroma Vector│
    │ (4-level)        │  │ Database     │
    │ + metadata       │  │              │
    │ enrichment       │  │data/chroma_db/
    └──────────────────┘  │(Embeddings)  │
                          └──────────────┘
                                 │
                        ┌────────┴──────────┐
                        ▼                   ▼
               ┌──────────────────┐  ┌──────────┐
               │   Ollama LLM     │  │HuggingF. │
               │ (mistral/...)    │  │Embeddings│
               │ Modello locale   │  │(e5-large)│
               └──────────────────┘  └──────────┘
```

**NEW v1.2 Features:**
- **Ingestion Layer:** Normalizzazione, validazione, deduplicazione, tracciabilità
- **Manifesto:** manifest.jsonl con 14 campi per piena audit trail
- **Organizzazione:** by_format/ + by_date/ per accesso intuitivo
- **Provenance:** Metadati arricchiti da ingestion a Chroma
- **Backward Compat:** Fallback a Documenti/ raw se ingestion non eseguito

---

## 🔄 Flusso Tecnico

### Flusso 1: Caricamento, Ingestion e Indicizzazione Documenti (v1.2)

```
┌──────────────────┐
│  Utente carica   │
│  documenti       │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────┐
│ POST /upload/ (con JWT)      │
│ Salva file in Documenti/     │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ POST /ingest/ (Admin-only)   │
│ Ingestion layer - NUOVO      │
│ (rag/ingestion.py)           │
│                              │
│ ✓ Normalizza nomi           │
│ ✓ Valida encoding (6-check)  │
│ ✓ Calcola SHA256 hash        │
│ ✓ Deduplica (content-based)  │
│ ✓ Organizza by_format/       │
│ ✓ Organizza by_date/         │
│ ✓ Genera manifest.jsonl      │
│ ✓ Tracciabilità completa     │
└────────┬─────────────────────┘
         │ Output: Documenti_ingested/
         │
         ▼
┌──────────────────────────────┐
│ GET /reindex/ (manuale)      │
│ O Crontab 03:00 (notturno)   │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ build_vector_db()            │
│ (indexing.py)                │
│                              │
│ 1. Carica documenti          │
│    Preferisce Documenti_     │
│    ingested/ con fallback a  │
│    Documenti/ (backward-compat)
│ 2. Arricchisce metadati      │
│    con provenance fields     │
│ 3. Filtra estensioni         │
│ 4. Valida encoding           │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ DynamicChunker (v1.1)        │
│ (rag/dynamic_chunking.py)    │
│                              │
│ Chunking adattivo - 4 livelli│
│ • Livello 1: Pagine          │
│ • Livello 2: Paragrafi       │
│ • Livello 3: Sezioni         │
│ • Livello 4: Frasi           │
│                              │
│ Smart split rispetto tipo    │
│ documento e struttura        │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ get_embeddings()             │
│ (embeddings.py - Singleton)  │
│                              │
│ HuggingFaceEmbeddings        │
│ Modello: intfloat/e5-large   │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ Chroma.add_documents()       │
│ Salva chunks nel vector DB   │
│ con metadati ARRICCHITI:     │
│ • source (original_path)     │
│ • file_hash                  │
│ • content_sha256             │
│ • ingestion_timestamp        │
│ • encoding                   │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ ✅ Reindex completato        │
│ DB vettoriale aggiornato     │
│ con piena tracciabilità      │
└──────────────────────────────┘
```

### Flusso 2: Query e Generazione Risposta

```
┌──────────────────────────┐
│ Utente scrive una        │
│ domanda in chat          │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ POST /chat/ (con JWT)            │
│ ChatRequest: prompt, top_k,      │
│ distance_threshold               │
└────────┬─────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ decide_from_db()                 │
│ (rag_query.py)                   │
│                                  │
│ 1. Controlla lunghezza prompt    │
│ 2. Aggiusta threshold dinamico   │
│ 3. Ricerca similarità (top_k)    │
│ 4. Richiede ≥2 match forti       │
│ 5. Ritorna True/False            │
└────────┬─────────────────────────┘
         │
    ┌────┴────┐
    │ Match?  │
    └────┬────┘
         │
    ┌────┴─────────────────────┐
    │ No                        │
    ▼                           ▼
 ┌───────────┐            ┌──────────────┐
 │ Ritorna   │            │ Procedi con  │
 │ "Non ho   │            │ RAG          │
 │ trovato"  │            └──────┬───────┘
 └───────────┘                   │
                                 ▼
                    ┌────────────────────────┐
                    │ query_rag()            │
                    │ (rag_query.py)         │
                    │                        │
                    │ 1. Similarity search   │
                    │    con embedding       │
                    │    della domanda       │
                    │                        │
                    │ 2. Filtra per soglia   │
                    │    distance_threshold  │
                    │                        │
                    │ 3. Seleziona max 5    │
                    │    chunk migliori      │
                    │                        │
                    │ 4. Costruisce contesto │
                    │    (prompt + fonti)    │
                    └────────┬───────────────┘
                             │
                             ▼
                    ┌────────────────────────┐
                    │ ChatOllama (Ollama)    │
                    │                        │
                    │ Invia prompt al LLM:   │
                    │ • System: ruolo legale │
                    │ • Context: chunks      │
                    │ • Question: domanda    │
                    │ • Temperature: 0       │
                    │   (deterministico)     │
                    └────────┬───────────────┘
                             │
                             ▼
                    ┌────────────────────────┐
                    │ LLM genera risposta    │
                    │                        │
                    │ Solo dalle fonti del   │
                    │ contesto RAG           │
                    └────────┬───────────────┘
                             │
                             ▼
                    ┌────────────────────────┐
                    │ Estrai sources metadata│
                    │ (file, distance,       │
                    │  chunk_index)          │
                    └────────┬───────────────┘
                             │
                             ▼
                    ┌────────────────────────┐
                    │ ChatResponse           │
                    │ {                      │
                    │  answer: "...",        │
                    │  sources: [...]        │
                    │ }                      │
                    └────────────────────────┘
```

### Flusso 3: Autenticazione Utente

```
┌──────────────────┐
│ Utente inserisce │
│ credenziali      │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────┐
│ POST /login              │
│ LoginRequest:            │
│  • username              │
│  • password              │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ Query DB Users table             │
│ SELECT * FROM users              │
│ WHERE username = ?               │
└────────┬─────────────────────────┘
         │
    ┌────┴────┐
    │ Trovato?│
    └────┬────┘
         │
    ┌────┴──────────────┐
    │ No               │ Sì
    ▼                  ▼
 ┌────────────┐   ┌─────────────────────┐
 │ Errore     │   │ verify_password()   │
 │ 401        │   │ (auth.py)           │
 └────────────┘   │                     │
                  │ bcrypt.checkpw()    │
                  │ plaintext vs hash   │
                  └────────┬────────────┘
                           │
                       ┌───┴───┐
                       │Valid? │
                       └───┬───┘
                           │
                    ┌──────┴──────┐
                    │ No         │ Sì
                    ▼            ▼
                 ┌────────┐  ┌──────────────┐
                 │Errore  │  │ create_jwt() │
                 │401     │  │ (auth.py)    │
                 └────────┘  │              │
                             │ Payload:     │
                             │ • username   │
                             │ • ruolo      │
                             │ • iat, exp   │
                             │              │
                             │ Firma con    │
                             │ SECRET_KEY   │
                             └──────┬───────┘
                                    │
                                    ▼
                             ┌────────────────┐
                             │ LoginResponse  │
                             │ {              │
                             │  token: "JWT"  │
                             │  username      │
                             │  ruolo         │
                             │ }              │
                             └────────────────┘
```

### Flusso 4: Validazione Token (Middleware)

```
┌────────────────────────┐
│ Richiesta API con      │
│ header Authorization   │
└────────┬───────────────┘
         │
         ▼
┌────────────────────────────┐
│ validate_token()           │
│ (auth.py - Dependency)     │
│                            │
│ Estrae token da header:    │
│ "Bearer <JWT>"             │
└────────┬───────────────────┘
         │
         ▼
┌────────────────────────────┐
│ jwt.decode(token,          │
│             SECRET_KEY)    │
│                            │
│ Verifica firma e scadenza  │
└────────┬───────────────────┘
         │
    ┌────┴──────────┐
    │ Valido?       │
    └────┬──────────┘
         │
    ┌────┴─────────────┐
    │ No              │ Sì
    ▼                 ▼
┌────────────┐  ┌─────────────┐
│ Errore 401 │  │ Ritorna     │
│ • Scaduto  │  │ payload     │
│ • Invalido │  │ (username,  │
└────────────┘  │  ruolo)     │
                └─────────────┘
                      │
                      ▼
                ┌──────────────┐
                │ Usa payload  │
                │ nell'endpoint│
                │ Verifica     │
                │ autorizzazioni│
                └──────────────┘
```

---

## 📦 Moduli Principali

### 1. **main.py** - Applicazione FastAPI principale

#### Responsabilità:
- Configurazione FastAPI e middleware CORS
- Gestione lifecycle (lifespan) con crontab notturno
- Definizione di tutti gli endpoints
- Mount del frontend statico

#### Componenti chiave:

| Componente | Descrizione |
|-----------|-------------|
| `lifespan()` | Context manager per startup/shutdown |
| `reindex_notturno()` | Task asincrono per reindex schedulato (03:00) |
| `@app.post("/chat/")` | Query RAG principale |
| `@app.post("/chat/stream")` | Query RAG con streaming |
| `@app.post("/upload/")` | Upload documenti (admin) |
| `@app.post("/ingest/")` | Ingestion layer - Normalizza/dedup (admin, NEW v1.2) |
| `@app.post("/login")` | Autenticazione utente |
| `@app.post("/registrazione")` | Registra nuovo utente (admin) |
| `@app.get("/lista-utenti")` | Lista utenti (admin) |
| `@app.put("/aggiorna-utente")` | Modifica utente (admin) |
| `@app.delete("/cancella-utente")` | Cancella utente (admin) |
| `@app.get("/reindex/")` | Reindex manuale (admin) |
| `@app.get("/debug_db/")` | Debug vettoriale |
| `@app.get("/get_models")` | Lista modelli LLM |
| `@app.post("/download_model")` | Scarica modello da Ollama |
| `@app.get("/get_parameters")` | Leggi parametri di sistema |
| `@app.post("/save_parameters")` | Salva parametri di sistema |

#### Middleware:
- **CORS**: Permette richieste da qualsiasi origine
- **Reindexing Check**: Blocca API durante reindex
- **Auth**: JWT validation su endpoint protetti

---

### 2. **auth.py** - Autenticazione e Autorizzazione

#### Responsabilità:
- Hash/verifica password con BCrypt
- Creazione e validazione JWT
- Dipendenza FastAPI per proteggere endpoint

#### Funzioni:

| Funzione | Parametri | Ritorno |
|----------|-----------|---------|
| `hash_password(pwd)` | password in chiaro | hash bcrypt |
| `verify_password(pwd, hash)` | password, hash | bool |
| `create_jwt(user, role)` | username, ruolo | JWT token |
| `validate_token(credentials)` | HTTPAuthorizationCredentials | payload dict |

#### JWT Payload:
```json
{
  "username": "admin",
  "ruolo": "admin",
  "iat": 1234567890,
  "exp": 1234567890 + 12h
}
```

---

### 3. **settings.py** - Configurazione e Modelli Pydantic

#### Responsabilità:
- Definizione modelli Pydantic (request/response)
- Caricamento parametri da DB (resolve_params)
- Configurazione percorsi directory
- Definizione direttiva di sistema (DIRETTIVA_PROMPT)

#### Modelli Pydantic:

```python
class LoginRequest:
    username: str
    password: str

class UserRequest:
    username: str
    password: str
    ruolo: str

class ChatRequest:
    prompt: str
    top_k: Optional[int] = None
    distance_threshold: Optional[float] = None
    llm_model: str = None  # Nuovo: permette override modello per query

class ChatResponse:
    answer: str
    sources: List[Dict[str, str]] = []
```

#### Funzione `resolve_params()`:
Legge da DB (ParameterDB) tutti i parametri di configurazione:

| Parametro | Default | Tipo | Descrizione |
|-----------|---------|------|-------------|
| `llm_model` | "mistral:latest" | string | Modello LLM attivo |
| `embed_model` | "intfloat/e5-large-v2" | string | Modello embedding |
| `chunk_size` | 1500 | int | Dimensione chunk (char) |
| `chunk_overlap` | 200 | int | Overlap tra chunk |
| `top_k` | 8 | int | N. chunk da recuperare |
| `distance_threshold` | 0.6 | float | Soglia similarità (0-1) |
| `excluded_exts` | ".md,.csv,.png,.jpg,.jpeg" | tuple | Estensioni escluse |
| `cron_reindex` | "0 3 * * *" | string | Reindex automatico (03:00) |
| `data_dir` | "Documenti" | Path | Cartella documenti |
| `DIRETTIVA_PROMPT` | "Tu sei RAGIS..." | string | Prompt di sistema per LLM |
| `Models` | ["mistral:latest", ...] | list | Modelli LLM disponibili |

#### DIRETTIVA_PROMPT

Prompt di sistema personalizzato per il modello LLM:
```
Tu sei RAGIS, un assistente virtuale con oltre 50 anni di esperienza 
amministrativa, tecnica e legale, specializzato nel supporto agli studi 
professionali...

REGOLE:
1. Rispondi sempre in modo conciso, tecnico e professionale
2. Analizza esclusivamente la documentazione fornita
3. Evidenzia criticità, scadenze, errori formali
4. Non generare conclusioni arbitrarie
5. Indica sempre i riferimenti documentali
```

Memorizzato in DB, modificabile via `POST /save_parameters`.

---

### 4.bis **rag/ingestion.py** - Normalizzazione Documenti (NEW v1.2)

#### Responsabilità:
- Normalizzazione documenti (nomi, struttura, encoding)
- Validazione 6-point check (esistenza, hidden, formato, size, vuoto, encoding)
- Deduplicazione content-based (SHA256)
- Organizzazione intelligente (by_format, by_date)
- Tracciabilità piena (manifest.jsonl con 14 campi)
- Idempotenza (skip duplicati in run successive)

#### Funzioni Pubbliche:

| Funzione | Input | Output |
|----------|-------|--------|
| `ingest_documents(source_dir, ingested_dir, deterministic)` | Request params | IngestionResponse |
| `sanitize_filename(filename)` | str | str (safe) |
| `is_valid_file(path)` | Path | bool |
| `detect_encoding(path)` | Path file | str (encoding) |

#### Processo Ingestion Dettagliato:

**Fase 1: Scansione**
- Ricerca ricorsiva in `Documenti/` (o dir custom)
- Raccoglie tutti i file (273 nel test)
- Applica filtri di esclusione (dir nascoste, etc.)

**Fase 2: Validazione (6 checks per ogni file)**
```
✓ File esiste e raggiungibile?
✓ Non è nascosto (non inizia con .)
✓ Formato supportato? (.pdf, .docx, .txt, .eml, .xlsx, .md, .html)
✓ Dimensione accettabile? (< 500 MB)
✓ Non vuoto? (0 bytes sono scartati)
✓ Encoding rilevabile? (chardet)
```

**Fase 3: Hash Calculation**
- Full SHA256: `hashlib.sha256(file_content)`
- Short hash: Prime 16 caratteri (per filename safety)
- Consulta manifest precedente per deduplication

**Fase 4: Organizzazione**
- `by_format/pdf/`, `by_format/docx/`, etc. (copia file)
- `by_date/YYYY-MM-DD/` (symlink su Unix, fallback copy su Windows)
- Nomi file: `{short_hash}_{sanitized_original_name}.{ext}`

**Fase 5: Manifest e Metadata**
- `manifest.jsonl`: 1 entry JSON per linea
- `metadata.json`: Statistiche globali

#### Manifest Entry (JSONL - 14 campi):

```json
{
  "original_path": "Avvocato/fattura_9.pdf",
  "ingested_path": "by_format/pdf/1a8a3246_fattura_9.pdf",
  "format": "pdf",
  "file_hash": "1a8a3246",
  "content_sha256": "1a8a3246cd...(full 64-char)",
  "file_size": 151363,
  "encoding": "utf-8",
  "ingestion_timestamp": "2025-12-16T12:45:43.743Z",
  "status": "valid",
  "validation_notes": "",
  "file_name": "fattura_9.pdf",
  "original_mtime": "2025-12-16T10:20:15.000Z",
  "is_duplicate_skip": false
}
```

#### Metadata JSON (statistiche):

```json
{
  "ingestion_timestamp": "2025-12-16T12:45:43.743Z",
  "total_files_found": 273,
  "total_files_ingested": 205,
  "total_files_skipped": 68,
  "total_files_corrupted": 0,
  "total_size_bytes": 82960000,
  "by_format": {
    "pdf": {"count": 145, "size_bytes": 72000000},
    "docx": {"count": 60, "size_bytes": 10960000}
  },
  "by_date": {...},
  "deterministic": true
}
```

#### Output Structure:

```
Documenti_ingested/
├── by_format/
│   ├── pdf/
│   │   ├── 1a8a3246_fattura_9.pdf
│   │   ├── 2b9b4357_relazione.pdf
│   │   └── ...
│   └── docx/
│       ├── e88c1fc7_relazione.docx
│       └── ...
├── by_date/
│   ├── 2025-12-16/
│   │   ├── 1a8a3246_fattura_9.pdf (→ symlink a by_format/...)
│   │   └── ...
│   └── 2025-12-15/
│       └── ...
├── manifest.jsonl (205 lines, 1 entry per file)
└── metadata.json (statistiche globali)
```

#### Idempotenza e Determinismo:

- **Content-based**: SHA256 sugli effettivi byte, non timestamp
- **Determinismo**: Timestamp fisso se `deterministic=True`
- **Deduplica**: Se hash già in manifest precedente, skip
- **Fallback**: Se symlink fallisce (Windows), copia file
- **Logging**: Completo di ogni decisione

#### Integrazione in Pipeline:

```
POST /ingest/ → ingest_documents()
  ↓
Documenti_ingested/ (normalizzato)
  ↓
POST /reindex/ → build_vector_db()
  ↓
load_all_documents() (legge da ingested, arricchisce metadata)
  ↓
Chroma DB (con provenance fields)
```

---

### 5. **rag/embeddings.py** - Gestione Embeddings e Vector DB

#### Responsabilità:
- Caricamento modello HuggingFace Embeddings (singleton)
- Inizializzazione Chroma DB persistente

#### Funzioni:

| Funzione | Descrizione |
|----------|-------------|
| `load_embedding_model(model_name)` | Carica e cachea modello HF (LRU cache) |
| `get_embeddings()` | Ritorna singleton embeddings |
| `get_vector_db()` | Ritorna singleton Chroma DB |

#### Singleton Pattern:
- `@lru_cache` per caching modelli
- Evita caricamenti ripetuti
- Migliora performance

---

### 6. **rag/loaders.py** - Caricamento Documenti (UPDATED v1.2)

#### Responsabilità:
- Supporto multiple formato file
- Hash file per deduplicazione
- **Preferenza Documenti_ingested/** (normalizzato) ← NEW
- Fallback a Documenti/ (backward compat) ← NEW
- Enrichment metadati da manifest.jsonl ← NEW
- Gestione errori caricamento

#### Funzioni:

| Funzione | Input | Output |
|----------|-------|--------|
| `load_manifest_entries(path)` | Path manifest.jsonl | Dict {ingested_path: entry} |
| `load_all_documents(request, base_dir)` | Request, Path dir | List[Document] con provenance |
| `smart_loader(path)` | Path file | Loader istanza |
| `get_file_hash(path)` | Path file | MD5 hexdigest |

#### Logica `load_all_documents()` (NEW in v1.2):
1. Verifica se `Documenti_ingested/` esiste
2. **Se sì:** Usa quello (preferenza)
   - Carica manifest.jsonl
   - Enrichisce metadati dei documenti
   - Log: "Usando Documenti_ingested/ (normalizzato)"
3. **Se no:** Fallback a `Documenti/`
   - Log: "Fallback a Documenti/ (nessun ingested trovato)"
4. Arricchisci metadata da manifest per ogni document:
   - `original_path`: Percorso originale (Documenti/...)
   - `file_hash`: SHA256 short hash (16 char)
   - `content_sha256`: Full hash (64 char)
   - `ingestion_timestamp`: ISO 8601 timestamp
   - `encoding`: Detected charset (utf-8, iso-8859-1, etc.)

#### Loader Supportati:

| Estensione | Loader |
|-----------|--------|
| `.pdf` | PyPDFLoader |
| `.docx`, `.doc` | UnstructuredWordDocumentLoader |
| `.txt` | TextLoader (UTF-8) |
| `.eml` | UnstructuredEmailLoader |
| `.xlsx`, `.xls` | UnstructuredExcelLoader |
| Altro | UnstructuredLoader (fallback) |

---

### 7. **rag/indexing.py** - Indicizzazione Vettoriale (UPDATED v1.2)

#### Responsabilità:
- Deduplicazione documenti (per hash)
- Chunking dinamico con 4 livelli ← IMPLEMENTED
- Aggiunta chunk a Chroma con provenance
- Logging della provenienza documenti ← NEW

#### Funzione: `build_vector_db()`

**Passi:**
1. Legge metadati esistenti da Chroma
2. **Carica tutti documenti** (NEW strategy):
   - Chiama `load_all_documents()` aggiornato
   - Preferisce `Documenti_ingested/` se esiste
   - Documenti enrichiti con provenance metadata (original_path, file_hash, timestamp, encoding)
3. Log della provenienza (NEW):
   - Se `has_original_path > 0`: "PROVENIENZA: X/Y documenti da Documenti_ingested/ (tracciabili)"
   - Else: "PROVENIENZA: Documenti caricati da Documenti/ (nessun ingestion)"
4. Filtra per estensioni escluse
5. Calcola hash file
6. Mantiene solo nuovi documenti (dedup)
7. Divide in chunk con **dynamic_chunking** (4 livelli)
8. Genera ID univoci (`{hash}-{chunk_index}`)
9. Salva in Chroma con metadati completi (source, hash, original_path, timestamp, encoding)

---

### 7. **rag/rag_query.py** - Query e Generazione Risposta

#### Responsabilità:
- Decisione uso RAG (threshold matching)
- Query similarità vettoriale
- Generazione risposta standard e streaming con LLM

#### Funzioni:

##### `decide_from_db(request, prompt, threshold, top_k)`
**Logica:**
1. Se prompt < 6 parole → threshold = min(threshold, 0.35) (più permissivo)
2. Ricerca similarità top_k
3. Filtra per threshold
4. Ritorna True se ≥2 match forti

##### `query_rag(request, question, top_k, distance_threshold, llm_model)`
**Logica:**
1. Ricerca similarità con embedding question
2. Filtra per distance_threshold
3. Seleziona max 5 chunk
4. Costruisce contesto con metadati (fonte, chunk_index, distanza)
5. Recupera `DIRETTIVA_PROMPT` dal DB
6. Invoca ChatOllama con:
   - System prompt: Direttiva personalizzata
   - Context: chunk filtrati
   - Question: domanda utente
   - Temperature: 0 (deterministico)
7. Ritorna: (answer_text, sources_metadata)

##### `query_rag_stream(request, question, top_k, distance_threshold, llm_model)`
**Async generator streaming:**
- Produzione token incrementale
- Interrompibile lato client
- Identica logica di query_rag ma con yield token per token
- Migliore UX per risposte lunghe

**Sources Metadata:**
```python
{
  "source": "Documenti/Clients/Bianchi_SRL/notifica_1.eml",
  "distance": "0.234",
  "chunk_index": "2"
}
```

---

### 7b. **rag/dynamic_chunking.py** - Chunking Intelligente

#### Responsabilità:
- Analisi struttura documenti (titoli, paragrafi, sezioni)
- Chunking semantico rispettando coesione logica
- 4 livelli di granularità (strutturale → ricorsivo)

#### Classe: `ChunkingConfig`

```python
@dataclass
class ChunkingConfig:
    min_chunk_tokens: int = 100        # ~400 char minimo
    max_chunk_tokens: int = 600        # ~2400 char massimo
    respect_structure: bool = True     # Rispetta paragrafi/titoli
    merge_small_chunks: bool = True    # Combina chunk < minimo
    include_context_headers: bool = True  # Aggiungi titolo
    section_markers: List[str] = ["#", "##", "Articolo", "Capo"]
    paragraph_threshold: int = 50      # Min char per paragrafo
```

#### Classe: `DynamicChunker`

| Metodo | Input | Output |
|--------|-------|--------|
| `chunk_documents(docs)` | List[Document] | List[Document] chunked |

**4 Livelli:**
1. **Strutturale:** Divide per sezioni (titoli, articoli)
2. **Paragrafale:** Mantiene paragrafi interi
3. **Sintattico:** Divide per frasi se paragrafo > max
4. **Ricorsivo:** Split conservativo come fallback

**Vantaggi vs chunking fisso:**
- Preserva contesto legale intero
- Evita frammentazione artificiale
- Migliora qualità retrieval (↑↑)
- Mantiene coesione semantica

---

### 8. **database/connection.py** - SQLite Connection (Singleton)

#### Responsabilità:
- Singleton pattern per connessione SQLite
- Thread-safe con Lock
- Row factory per accesso colonne per nome

#### Classe: `DBConnection`

```python
class DBConnection:
    _instance = None
    _lock = Lock()
    
    def __new__(cls, db_path="db_sql/app.db"):
        # Singleton pattern con thread-safety
        
    def cursor(self):
        return self.conn.cursor()
```

**Configurazione:**
- Database: `db_sql/app.db`
- Row Factory: `sqlite3.Row` (accesso dict-like)
- Thread-safe: `check_same_thread=False`

---

### 9. **database/migration.py** - Creazione Schema

#### Responsabilità:
- Creazione tabelle (idempotent)
- Inserimento utente admin default

#### Funzione: `run_migrations()`

**Tabelle create:**

##### `users`
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    ruolo TEXT DEFAULT 'user',
    data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

##### `parameters`
```sql
CREATE TABLE parameters (
    nome TEXT PRIMARY KEY,
    valore TEXT NOT NULL,
    tipo TEXT DEFAULT 'string',
    descrizione TEXT,
    data_aggiornamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Utente default:**
- Username: `admin`
- Password: `Ragis@2025Admin`
- Ruolo: `admin`
- Hash: BCrypt (sicuro)

---

### 10. **database/parameter_db.py** - Gestione Parametri

#### Responsabilità:
- CRUD parametri configurazione
- Persistenza DB

#### Classe: `ParameterDB`

| Metodo | Parametri | Descrizione |
|--------|-----------|-------------|
| `get(name, default)` | nome parametro | Ritorna valore o default |
| `set(nome, valore, tipo, descrizione)` | parametro | Inserisce o aggiorna |

**Esempio:**
```python
db = ParameterDB()
db.set("llm_model", "mistral", tipo="string", descrizione="Modello LLM")
model = db.get("llm_model", "mistral")  # → "mistral"
```

---

### 11. **logger_ragis/rag_log.py** - Logging

#### Responsabilità:
- Configurazione logger Python
- Log strutturato per debug

#### Utilizzo:
```python
log = RagLog.get_logger("module_name")
log.info("Messaggio")
log.exception("Errore con stack trace")
```

---

## 🔌 API Endpoints

### Autenticazione

#### `POST /login`
**Autenticazione e generazione JWT**

Request:
```json
{
  "username": "admin",
  "password": "Ragis@2025Admin"
}
```

Response:
```json
{
  "token": "eyJhbGc...",
  "username": "admin",
  "ruolo": "admin"
}
```

Status: `200 OK` | `401 Unauthorized`

---

### Ingestion (Protetto - Admin)

#### `POST /ingest/`
**Normalizza, valida e deduplica documenti**

Headers: `Authorization: Bearer {JWT}`

Request (opzionale):
```json
{
  "source_dir": "Documenti",
  "ingested_dir": "Documenti_ingested",
  "deterministic": true
}
```

Response:
```json
{
  "success": true,
  "total_files_found": 273,
  "files_ingested": 205,
  "files_skipped": 68,
  "files_corrupted": 0,
  "manifest_path": "Documenti_ingested/manifest.jsonl",
  "metadata_path": "Documenti_ingested/metadata.json",
  "summary": {
    "by_format": {"pdf": 145, "docx": 60},
    "total_size_mb": 82.96
  }
}
```

**Processi:**
1. **Normalizzazione**: Riordina file per coesione logica, sanitizza nomi
2. **Validazione** (6-point check):
   - File esiste e raggiungibile
   - Non è nascosto (hidden)
   - Formato supportato (.pdf, .docx, .txt, .eml, .xlsx, .md, .html)
   - Dimensione accettabile (< 500 MB)
   - Non vuoto (0 bytes skip)
   - Encoding rilevabile (UTF-8, ISO-8859-1, CP1252, Latin-1)
3. **Deduplicazione** (content-based):
   - Calcola SHA256 full + short (16 char)
   - Skip se hash già visto in ingestion precedente
4. **Organizzazione**:
   - `by_format/pdf/`, `by_format/docx/`, etc.
   - `by_date/2025-12-16/`, `by_date/2025-12-15/`, etc.
   - Symlink (Windows: fallback copy)
5. **Tracciabilità**:
   - `manifest.jsonl`: 1 entry JSON per file (14 campi)
   - `metadata.json`: Statistiche globali per_format

**Output Structure:**
```
Documenti_ingested/
├── by_format/
│   ├── pdf/
│   │   ├── 1a8a3246_fattura.pdf
│   │   └── ...
│   └── docx/
│       ├── e88c1fc7_relazione.docx
│       └── ...
├── by_date/
│   ├── 2025-12-16/
│   │   ├── 1a8a3246_fattura.pdf
│   │   └── ...
│   └── 2025-12-15/
│       └── ...
├── manifest.jsonl
└── metadata.json
```

**Manifest Entry (JSONL - one per line):**
```json
{
  "original_path": "Avvocato/fattura_9.pdf",
  "ingested_path": "by_format/pdf/1a8a3246_fattura_9.pdf",
  "format": "pdf",
  "file_hash": "1a8a3246",
  "content_sha256": "1a8a3246...(full SHA256)",
  "file_size": 151363,
  "encoding": "utf-8",
  "ingestion_timestamp": "2025-12-16T12:45:43.743Z",
  "status": "valid",
  "validation_notes": ""
}
```

Status: `200 OK` | `401 Unauthorized` | `403 Forbidden`

---

#### `POST /chat/`
**Query RAG principale (risposta completa)**

Headers: `Authorization: Bearer {JWT}`

Request:
```json
{
  "prompt": "Quali sono i termini di pagamento secondo la notifica ricevuta?",
  "top_k": 5,
  "distance_threshold": 0.6,
  "llm_model": "mistral:latest"
}
```

Response:
```json
{
  "answer": "Secondo la notifica ricevuta, i termini di pagamento sono...",
  "sources": [
    {
      "source": "Documenti/Clients/Bianchi_SRL/notifica_1.eml",
      "distance": "0.234",
      "chunk_index": "2"
    }
  ]
}
```

Status: `200 OK` | `401 Unauthorized` | `400 Bad Request`

---

#### `POST /chat/stream`
**Query RAG con streaming (risposta incrementale)**

Headers: `Authorization: Bearer {JWT}`

Request: (identico a `/chat/`)

Response: `text/plain` stream
```
Non ho trovato informazioni rilevanti nei documenti.
Token1 Token2 Token3 ... (streaming incrementale)
```

Status: `200 OK` | `401 Unauthorized`

**Vantaggi:**
- Risposta in tempo reale (token per token)
- Migliore UX per risposte lunghe
- Interrompibile lato client (CancelledError)
- Ideale per UI reattivi

---

### Upload (Protetto - Admin)

#### `POST /upload/`
**Carica documenti**

Headers: `Authorization: Bearer {JWT}`

Multipart form-data:
- `files`: lista file

Response:
```json
{
  "messagio": "Upload completato.",
  "files_salvati": ["notifica_5.eml", "contratto.pdf"]
}
```

Status: `200 OK` | `401 Unauthorized` | `403 Forbidden`

---

### Indicizzazione (Protetto - Admin)

#### `GET /reindex/`
**Reindex manuale database vettoriale (con chunking dinamico)**

Headers: `Authorization: Bearer {JWT}`

Response:
```json
{
  "message": "Indicizzati 3 nuovi documenti (tot chunk: 45).",
  "strategy": "dynamic_chunking"
}
```

Status: `200 OK` | `500 Internal Server Error`

**Nota:** Usa automaticamente `use_dynamic_chunking=True` per migliore qualità.

---

### Gestione Modelli LLM (Protetto - Admin)

#### `GET /get_models`
**Elenca modelli Ollama disponibili con stato installazione**

Headers: `Authorization: Bearer {JWT}`

Response:
```json
{
  "models": [
    {
      "name": "mistral:latest",
      "installed": true
    },
    {
      "name": "llama3.2:latest",
      "installed": true
    },
    {
      "name": "qwen2.5:latest",
      "installed": false
    },
    {
      "name": "gemma2:2b",
      "installed": true
    },
    {
      "name": "phi3:latest",
      "installed": true
    }
  ]
}
```

Status: `200 OK` | `401 Unauthorized`

---

#### `POST /download_model`
**Scarica e installa un modello Ollama**

Headers: `Authorization: Bearer {JWT}`

Request:
```json
{
  "model_name": "qwen2.5:latest"
}
```

Response:
```json
{
  "message": "Modello 'qwen2.5:latest' scaricato e impostato come attivo."
}
```

Status: `200 OK` | `401 Unauthorized`

**Nota:** Operazione asincrona, può richiedere minuti. Monitora il download tramite `GET /get_models`.

---

### Debug (Public)

#### `GET /debug_db/`
**Statistiche vector database**

Response:
```json
{
  "documenti": 150,
  "metadati_sample": [
    {"source": "...", "hash": "..."},
    ...
  ]
}
```

---

### Gestione Utenti (Protetto - Admin)

#### `POST /registrazione`
**Registra nuovo utente**

Headers: `Authorization: Bearer {JWT}`

Request:
```json
{
  "username": "mario_rossi",
  "password": "SecurePassword123",
  "ruolo": "user"
}
```

Response:
```json
{
  "messaggio": "Registrazione completata"
}
```

Status: `200 OK` | `400 Bad Request` | `403 Forbidden`

---

#### `GET /lista-utenti`
**Elenca utenti del sistema**

Headers: `Authorization: Bearer {JWT}`

Response:
```json
{
  "utenti": [
    {
      "id": 1,
      "username": "admin",
      "password_hash": "$2b$...",
      "ruolo": "admin"
    },
    {
      "id": 2,
      "username": "mario_rossi",
      "password_hash": "$2b$...",
      "ruolo": "user"
    }
  ]
}
```

Status: `200 OK` | `403 Forbidden`

---

#### `PUT /aggiorna-utente/{user_id}`
**Modifica dati utente**

Headers: `Authorization: Bearer {JWT}`

Request:
```json
{
  "username": "mario_rossi_2",
  "password": "NewPassword456",
  "ruolo": "user"
}
```

Response:
```json
{
  "messaggio": "Utente aggiornato correttamente"
}
```

Status: `200 OK` | `404 Not Found` | `403 Forbidden`

---

#### `DELETE /cancella-utente/{user_id}`
**Cancella utente**

Headers: `Authorization: Bearer {JWT}`

Response:
```json
{
  "messaggio": "Utente cancellato con successo"
}
```

Status: `200 OK` | `404 Not Found` | `403 Forbidden`

---

---

### Parametri (Protetto - Admin)

#### `GET /get_parameters`
**Recupera tutti i parametri di sistema**

Headers: `Authorization: Bearer {JWT}`

Response:
```json
{
  "llm_model": "mistral:latest",
  "embed_model": "intfloat/e5-large-v2",
  "chunk_size": 1500,
  "chunk_overlap": 200,
  "top_k": 8,
  "distance_threshold": 0.6,
  "excluded_exts": [".md", ".csv", ".png", ".jpg", ".jpeg"],
  "cron_reindex": "0 3 * * *",
  "data_dir": "/path/to/Documenti",
  "DIRETTIVA_PROMPT": "Tu sei RAGIS, un assistente...",
  "Models": ["mistral:latest", "llama3.2:latest", "qwen2.5:latest", "gemma2:2b", "phi3:latest"]
}
```

Status: `200 OK` | `401 Unauthorized`

---

#### `POST /save_parameters`
**Salva parametri configurazione (atomico)**

Headers: `Authorization: Bearer {JWT}`

Request (qualsiasi subset):
```json
{
  "llm_model": "llama3.2:latest",
  "top_k": "10",
  "distance_threshold": "0.5",
  "chunk_size": "2000",
  "cron_reindex": "0 2 * * *"
}
```

Response:
```json
{
  "message": "Parametri salvati con successo"
}
```

Status: `200 OK` | `401 Unauthorized`

**Nota:** Tutti i parametri sono salvati nel DB e persistono tra i riavvii.

---

### Frontend (Public)

#### `GET /`
**Serve interfaccia React**

Response: `index.html` da `frontend_dist/`

Status: `200 OK` | `404 Not Found`

---

## 💾 Database

### Schema SQLite

#### Tabella: `users`
| Colonna | Tipo | Vincoli |
|---------|------|---------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `username` | TEXT | UNIQUE NOT NULL |
| `password_hash` | TEXT | NOT NULL |
| `ruolo` | TEXT | DEFAULT 'user' |
| `data_creazione` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

**Indici implicititi:** PRIMARY KEY e UNIQUE su username

**Ruoli:**
- `admin`: Accesso completo (manage utenti, upload, reindex)
- `user`: Solo query RAG

---

#### Tabella: `parameters`
| Colonna | Tipo | Vincoli |
|---------|------|---------|
| `nome` | TEXT | PRIMARY KEY |
| `valore` | TEXT | NOT NULL |
| `tipo` | TEXT | DEFAULT 'string' |
| `descrizione` | TEXT | NULL |
| `data_aggiornamento` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

**Parametri standard:**
- `llm_model`: Modello Ollama (string)
- `embed_model`: Modello HuggingFace (string)
- `chunk_size`: Dimensione chunk (number)
- `chunk_overlap`: Overlap chunk (number)
- `top_k`: Top K similari (number)
- `distance_threshold`: Soglia distanza (decimal)
- `excluded_exts`: Estensioni escluse (tupla/string)
- `cron_reindex`: Crontab schedule (string)
- `DATA_DIR`: Cartella documenti (string)

---

### Vector Database (Chroma)

**Percorso:** `data/chroma_db/`

**Persistenza:** Disco locale (SQLite + parquet)

**Struttura:**
- **Collections:** Documento → Chunks
- **Embeddings:** HuggingFace e5-large-v2
- **Metadati per chunk:**
  ```json
  {
    "source": "Documenti/file.pdf",
    "hash": "d41d8cd98f00b204e9800998ecf8427e",
    "chunk_index": 5
  }
  ```

**Query:** Similarity search (cosine distance)

---

## 🔐 Autenticazione e Autorizzazione

### Flusso Autenticazione

1. **Login:** POST `/login` → genera JWT (valido 12 ore)
2. **Request:** Allega JWT in header `Authorization: Bearer {token}`
3. **Validazione:** Middleware verifica firma e scadenza
4. **Autorizzazione:** Endpoint verifica ruolo da payload JWT

### Ruoli e Permessi

| Endpoint | Public | User | Admin |
|----------|--------|------|-------|
| POST /login | ✅ | ✅ | ✅ |
| POST /chat | ❌ | ✅ | ✅ |
| POST /upload | ❌ | ❌ | ✅ |
| GET /reindex | ❌ | ❌ | ✅ |
| POST /registrazione | ❌ | ❌ | ✅ |
| GET /lista-utenti | ❌ | ❌ | ✅ |
| PUT /aggiorna-utente | ❌ | ❌ | ✅ |
| DELETE /cancella-utente | ❌ | ❌ | ✅ |
| POST /save_parameters | ❌ | ❌ | ✅ |
| GET /debug_db | ✅ | ✅ | ✅ |
| GET / | ✅ | ✅ | ✅ |

### Sicurezza Password

- **Hashing:** BCrypt con salt (gensalt())
- **Verifica:** bcrypt.checkpw() (constant-time comparison)
- **Non reversibile:** Hash non può tornare a password

### JWT

- **Algoritmo:** HS256 (HMAC-SHA256)
- **Secret Key:** "Ragis2027" (⚠️ Cambiarla in produzione!)
- **TTL:** 12 ore
- **Payload:** username, ruolo, iat (issued at), exp (expiration)

---

## ⚙️ Configurazione

### Variabili Ambiente

```bash
# Directory base applicazione
BASE_DIR=/path/to/RAGIS

# Directory database Chroma (vector store)
DB_DIR=/path/to/RAGIS/data/chroma_db
```

### Parametri Configurabili (Database)

Tutti i parametri sono salvati nella tabella `parameters` di SQLite e possono essere modificati tramite:

#### 1. Via API (Runtime)
```bash
curl -X POST http://localhost:8000/save_parameters \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "llm_model": "llama3.2:latest",
    "top_k": "10",
    "distance_threshold": "0.5"
  }'
```

#### 2. Via Python (Setup iniziale)
```python
from database.parameter_db import ParameterDB

db = ParameterDB()
db.set("llm_model", "mistral:latest", tipo="string", descrizione="Modello LLM")
db.set("top_k", "8", tipo="number", descrizione="Top K chunk")
db.set("chunk_size", "1500", tipo="number", descrizione="Dimensione chunk")
```

#### 3. Leggere parametri
```python
from settings import resolve_params

params = resolve_params()
print(params["llm_model"])  # → "mistral:latest"
print(params["chunk_size"])  # → 1500
```

### File Configurazione

| File | Funzione |
|------|----------|
| `requirements.txt` | Dipendenze Python (pip install) |
| `settings.py` | Modelli Pydantic e resolve_params() |
| `Documenti/` | Directory input documenti (configurabile) |
| `data/chroma_db/` | Vector database persistente |
| `db_sql/app.db` | Database SQLite (users, parameters) |
| `logs/` | Log applicazione (RagLog) |

### Reindex Automatico (Crontab)

Configurato in parametro `cron_reindex` (default: `"0 3 * * *"` = 03:00 ogni giorno):

```
# Ogni giorno alle 03:00
0 3 * * *

# Format crontab standard: MM HH DD MM WEEKDAY
# Ogni 2 ore
0 */2 * * *

# Ogni 6 ore
0 0,6,12,18 * * *
```

**Processo:**
1. Applicazione carica il cron al startup (lifespan)
2. Attiva automaticamente `reindex_notturno()` all'ora specificata
3. Durante reindex, middleware blocca tutte le API (ritorna "Sistema in aggiornamento")
4. Dopo completamento, API riprendono normalmente

---

## 🧩 Chunking Dinamico

### Motivazione

Il **chunking fisso** (dimensione fissa) compromette la qualità dei risultati:
- Titoli + 1 frase = insufficiente per il retrieval
- Frasi tagliate nel mezzo perdono coesione semantica
- Paragrafi interi preservano il contesto legale

### Architettura DynamicChunker

La classe `DynamicChunker` in [rag/dynamic_chunking.py](rag/dynamic_chunking.py) implementa 4 livelli:

#### **LIVELLO 1: Strutturale**
- Divide per sezioni (titoli `#`, `##`, articoli, capitoli)
- Preserva titolo come contesto per paragrafi successivi
- Mantiene coesione logica del documento

#### **LIVELLO 2: Paragrafale**
- Mantiene paragrafi interi se < max_size (600 token ≈ 2400 char)
- Combina paragrafi piccoli al precedente
- Evita frammentazione artificiale

#### **LIVELLO 3: Sintattico**
- Se paragrafo > max_size: divide per frasi
- Intelligente: evita tagli in mezzo a parentesi/numeri
- Preserva significato semantico

#### **LIVELLO 4: Ricorsivo Fallback**
- Se frase > max: split ricorsivo conservativo
- Ultima risorsa per contenuti densissimi

### Configurazione ChunkingConfig

```python
@dataclass
class ChunkingConfig:
    min_chunk_tokens: int = 100        # ~400 char minimo
    max_chunk_tokens: int = 600        # ~2400 char massimo
    respect_structure: bool = True     # Rispetta paragrafi/titoli
    merge_small_chunks: bool = True    # Combina chunk piccoli
    include_context_headers: bool = True  # Aggiungi titolo al paragrafo
    section_markers: List[str] = [...]   # Marcatori sezione
    paragraph_threshold: int = 50      # Minimo char per paragrafo
```

### Vantaggi

| Aspetto | Fisso | Dinamico |
|---------|-------|----------|
| Qualità retrieval | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Coesione semantica | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Contesto paragrafo | ⭐ | ⭐⭐⭐⭐⭐ |
| Ridondanza | Alta | Bassa |
| Velocità indicizzazione | Veloce | Normale |

### Utilizzo nel Flusso

```
Documento caricato
      ↓
build_vector_db(use_dynamic_chunking=True)
      ↓
load_all_documents()
      ↓
DynamicChunker.chunk_documents()
      ↓
Analizza struttura (titoli, paragrafi, frasi)
      ↓
Genera chunk coesivi (100-600 token)
      ↓
Aggiungi embedding e metadati
      ↓
Salva in Chroma DB
```

**Nota:** Il reindex notturno (03:00) usa automaticamente `use_dynamic_chunking=True` per qualità ottimale.

---

## 🚀 Guida All'Uso

### Setup Iniziale

1. **Clone repository:**
   ```bash
   git clone <repo-url>
   cd RAGIS
   ```

2. **Crea venv e installa dipendenze:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Avvia Ollama (modelli locali):**
   ```bash
   ollama pull mistral
   ollama serve
   ```

4. **Avvia backend FastAPI:**
   ```bash
   python main.py
   # Accedi a http://localhost:8000
   ```

5. **Build e avvia frontend (opzionale):**
   ```bash
   cd frontend/rag-interface
   npm install
   npm run build
   npm start
   ```

### Primo Accesso

- **URL:** http://localhost:8000
- **Username:** `admin`
- **Password:** `Ragis@2025Admin`
- **Ruolo:** `admin`

### Workflow Tipico (v1.2 - Con Ingestion Layer)

#### 1. Admin carica documenti
- Login come `admin`
- POST `/upload/` con file (PDF, Word, Email, Excel, TXT)
- File salvati in `Documenti/` (grezzo, non normalizzato)

#### 1.bis. Admin esegue INGESTION (NEW v1.2)
- **Comando:** POST `/ingest/` (admin-only)
- **Input:** Source dir `Documenti/`, Output dir `Documenti_ingested/`
- **Processi:**
  - Normalizzazione file (nomi, encoding)
  - Validazione 6-point check per ogni file
  - Deduplicazione content-based (SHA256)
  - Organizzazione intelligente:
    - `by_format/pdf/`, `by_format/docx/`, etc.
    - `by_date/2025-12-16/`, `by_date/2025-12-15/`, etc.
  - Generazione manifest.jsonl (14 campi per file)
  - Generazione metadata.json (statistiche globali)
- **Output:** Documenti_ingested/ + manifest.jsonl + metadata.json
- **Idempotenza:** Skip file già processati (based on hash)
- **Tracciabilità:** Ogni documento ha original_path, hash, timestamp, encoding

#### 2. Sistema indicizza automaticamente o manualmente
- **Automatico:** Crontab giornaliero (03:00 default)
- **Manuale:** Admin chiama GET `/reindex/`
- **Caricamento Documenti (NEW v1.2):**
  - Preferisce `Documenti_ingested/` (normalizzato)
  - Fallback a `Documenti/` se ingestion non eseguito (backward compat)
  - Arricchisce metadati da manifest.jsonl:
    - original_path, file_hash, content_sha256, ingestion_timestamp, encoding
- **Chunking Adattivo:** DynamicChunker 4-level (rispetta struttura documento)
- Documenti convertiti in chunk coesivi (100-600 token)
- Embedding calcolati (intfloat/e5-large-v2)
- Salvati in Chroma con metadati ARRICCHITI (source, hash, chunk_index, original_path, timestamp)

#### 3. User fa domanda
- Login (user o admin)
- POST `/chat/` per risposta completa
- O POST `/chat/stream` per risposta streaming
- Sistema ricerca chunk simili (similarity_search_with_score)
- LLM genera risposta da contesto RAG
- Risposta inclusa insieme alle fonti
- **NEW:** Fonti tracciabili fino al documento originale via original_path

#### 4. Admin gestisce modelli LLM
- GET `/get_models/` → vedi modelli installati/disponibili
- POST `/download_model` → scarica nuovo modello da Ollama Hub
- Modifica `llm_model` in parametri per cambiare modello attivo
- Tutti i modelli nella lista `Models` sono disponibili

#### 5. Admin gestisce utenti
- POST `/registrazione/` → crea nuovo user
- PUT `/aggiorna-utente/{id}` → modifica username/password/ruolo
- DELETE `/cancella-utente/{id}` → cancella user
- GET `/lista-utenti/` → visualizza tutti gli user

#### 6. Admin configura parametri
- GET `/get_parameters/` → leggi configurazione corrente
- POST `/save_parameters` → modifica parametri
- Parametri persistono nel DB tra i riavvii

### Query RAG Standard vs Streaming

#### Risposta Completa (`/chat/`)
```bash
curl -X POST http://localhost:8000/chat/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Quali sono i termini di pagamento?",
    "top_k": 5,
    "distance_threshold": 0.6,
    "llm_model": "mistral:latest"
  }'

# Response immediata con answer completa + sources
```

#### Risposta Streaming (`/chat/stream`)
```bash
curl -X POST http://localhost:8000/chat/stream \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Quali sono i termini di pagamento?",
    "top_k": 5,
    "distance_threshold": 0.6
  }'

# Response token-by-token in tempo reale
```

**Quando usare:**
- `/chat/`: Risposte brevi, API batch, integrazioni
- `/chat/stream`: Frontend React, UX reattiva, risposte lunghe

---

## 📊 Flusso di Dati Globale

```
┌─────────────────────────────────────────────────────────────┐
│                      FRONTEND (React)                       │
│  • Login form                                               │
│  • Chat interface                                           │
│  • Admin panel (user management, upload)                    │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
   ┌─────────┐  ┌─────────┐  ┌─────────────┐
   │  Login  │  │  Chat   │  │  Upload     │
   │         │  │         │  │             │
   │ /login  │  │ /chat/  │  │ /upload/    │
   └────┬────┘  └────┬────┘  └──────┬──────┘
        │            │              │
        ▼            ▼              ▼
   ┌─────────────────────────────────────┐
   │  AUTH LAYER                         │
   │  • validate_token() dependency      │
   │  • Verifica JWT                     │
   │  • Check ruolo                      │
   └─────────────────────────────────────┘
        │            │              │
        ▼            ▼              ▼
   ┌────────────┬──────────┬───────────┐
   │  DBConnection  │ RAG Module      │ Settings
   │  (SQLite)      │ (embeddings,    │ (Params)
   │                │  loaders,       │
   │  • users table │  indexing,      │
   │  • params      │  rag_query)     │
   │                │                 │
   └────────────────┼─────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
   ┌──────────────┐      ┌─────────────────┐
   │  Chroma DB   │      │  Ollama LLM     │
   │ (Embeddings) │      │ (Generazione)   │
   │              │      │                 │
   │ Vector data  │      │ • mistral       │
   │ Persistente  │      │ • llama2        │
   │              │      │ • Altro         │
   └──────────────┘      └─────────────────┘
        │
        ▼
   ┌──────────────────┐
   │ Documenti/       │
   │ (Input files)    │
   │                  │
   │ • PDF            │
   │ • Word           │
   │ • Email          │
   │ • Excel          │
   │ • TXT            │
   └──────────────────┘
```

---

## 🎓 Esempi Pratici

### Esempio 1: Setup iniziale e primo login

```bash
# 1. Avvia Ollama (in un altro terminale)
ollama serve

# 2. Avvia backend RAGIS
python main.py
# Server avviato su http://localhost:8000

# 3. Login come admin
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Ragis@2025Admin"}'

# Response
# {
#   "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
#   "username": "admin",
#   "ruolo": "admin"
# }
```

### Esempio 2: Registrazione nuovo user e upload documento

```bash
# 1. Registra nuovo user (come admin)
curl -X POST http://localhost:8000/registrazione \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGc..." \
  -d '{
    "username":"mario_rossi",
    "password":"SecurePassword123",
    "ruolo":"user"
  }'

# 2. Upload documento (come admin)
curl -X POST http://localhost:8000/upload/ \
  -H "Authorization: Bearer eyJhbGc..." \
  -F "files=@contratto.pdf" \
  -F "files=@notifica.eml"

# Response
# {
#   "messagio": "Upload completato.",
#   "files_salvati": ["contratto.pdf", "notifica.eml"]
# }

# 3. Reindex manuale con chunking dinamico
curl -X GET http://localhost:8000/reindex/ \
  -H "Authorization: Bearer eyJhbGc..."

# Response
# {
#   "message": "Indicizzati 2 nuovi documenti (tot chunk: 34).",
#   "strategy": "dynamic_chunking"
# }
```

### Esempio 3: Query RAG standard vs streaming

```bash
# Query 1: Risposta completa
curl -X POST http://localhost:8000/chat/ \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Quali sono i termini di pagamento nel contratto?",
    "top_k": 5,
    "distance_threshold": 0.6
  }'

# Response
# {
#   "answer": "Secondo il contratto, i termini di pagamento sono...",
#   "sources": [
#     {
#       "source": "Documenti/contratto.pdf",
#       "distance": "0.234",
#       "chunk_index": "3"
#     }
#   ]
# }

# Query 2: Risposta streaming (token per token)
curl -X POST http://localhost:8000/chat/stream \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Quali sono i termini di pagamento nel contratto?",
    "top_k": 5,
    "distance_threshold": 0.6
  }'

# Response (stream)
# Non ho trovato informazioni rilevanti nei documenti.
# Secondo il contratto, i termini...
# di pagamento sono entro 30 giorni...
# (continua token per token)
```

### Esempio 4: Gestione modelli LLM

```bash
# 1. Visualizza modelli disponibili
curl -X GET http://localhost:8000/get_models \
  -H "Authorization: Bearer eyJhbGc..."

# Response
# {
#   "models": [
#     {"name": "mistral:latest", "installed": true},
#     {"name": "llama3.2:latest", "installed": true},
#     {"name": "qwen2.5:latest", "installed": false},
#     {"name": "gemma2:2b", "installed": true}
#   ]
# }

# 2. Scarica nuovo modello
curl -X POST http://localhost:8000/download_model \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "Content-Type: application/json" \
  -d '{"model_name": "qwen2.5:latest"}'

# Response
# {
#   "message": "Modello 'qwen2.5:latest' scaricato e impostato come attivo."
# }

# 3. Cambia modello attivo nei parametri
curl -X POST http://localhost:8000/save_parameters \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "Content-Type: application/json" \
  -d '{"llm_model": "qwen2.5:latest"}'

# Response
# {
#   "message": "Parametri salvati con successo"
# }
```

### Esempio 5: Modifica parametri di sistema

```python
from database.parameter_db import ParameterDB
from settings import resolve_params

db = ParameterDB()

# Cambio modello embedding (richiede reindicizzazione)
db.set("embed_model", "bge-small-en-v1.5", tipo="string")

# Cambio soglia similarità (più permissivo)
db.set("distance_threshold", "0.5", tipo="decimal")

# Cambio top_k (più chunk da recuperare)
db.set("top_k", "10", tipo="number")

# Cambio schedule reindex (ogni 6 ore)
db.set("cron_reindex", "0 */6 * * *", tipo="string")

# Cambia dimensione chunk (per nuove indicizzazioni)
db.set("chunk_size", "2000", tipo="number")

# Leggi parametri aggiornati
params = resolve_params()
print(f"Modello LLM: {params['llm_model']}")
print(f"Top K: {params['top_k']}")
print(f"Distance threshold: {params['distance_threshold']}")
```

### Esempio 6: Configurazione direttiva personalizzata

```bash
curl -X POST http://localhost:8000/save_parameters \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "Content-Type: application/json" \
  -d '{
    "DIRETTIVA_PROMPT": "Tu sei RAGIS, specializzato in diritto commerciale e contrattualistica. Rispondi sempre in italiano, usando linguaggio tecnico-legale. Se il documento non contiene informazioni, dillo esplicitamente. Cita sempre gli articoli o le clausole di riferimento."
  }'

# Questa direttiva verrà usata in tutte le successive query RAG
```

---

## 🐛 Troubleshooting

### Problema: "Ollama not available" / Connection refused
**Soluzione:** 
```bash
# Terminal separato
ollama serve

# Verifica che sia in ascolto
curl http://localhost:11434/api/tags
# Deve ritornare: {"models": [...]}
```

### Problema: "Token scaduto"
**Soluzione:** 
- JWT valido 12 ore
- Login di nuovo: `POST /login`
- Nuovo token sarà valido per altre 12 ore

### Problema: Reindex bloccato / "Sistema in aggiornamento"
**Soluzione:**
- Attendere che il reindex termini (vedi logs)
- Se bloccato > 30 min: interrompi server, cancella lock manuali
- Verifica log in `logs/app.log.*`

### Problema: "Nessun documento trovato" / risultati vuoti
**Soluzione:** 
1. Verifica che documenti siano in `Documenti/` (config via `data_dir`)
2. Controlla che non siano in estensioni escluse: `GET /get_parameters` → `excluded_exts`
3. Esegui reindex manuale: `GET /reindex/`
4. Verifica metadati: `GET /debug_db/`

### Problema: Chunking produce risultati peggiori
**Soluzione:**
- Verifica dimensioni chunk: `chunk_size` (default 1500 char)
- Aumenta `top_k` per recuperare più chunk
- Abbassa `distance_threshold` per risultati più permissivi
- Modifica `ChunkingConfig` in `rag/dynamic_chunking.py` se necessario

### Problema: Modello LLM lento / timeout
**Soluzione:**
1. Verifica modello: `GET /get_models`
2. Scegli modello più veloce (es. phi3:2.7b vs mistral)
3. Cambia modello: `POST /save_parameters` con `llm_model`
4. Aumenta timeout in FastAPI se necessario

### Problema: "Database locked" (SQLite)
**Soluzione:**
- SQLite a volte ha contention
- Riavvia server: `python main.py`
- Verifica che nessun altro processo usi `db_sql/app.db`

### Problema: Risposte LLM off-topic / poco rilevanti
**Soluzione:**
1. Abbassa `distance_threshold` (default 0.6 → prova 0.5)
2. Aumenta `top_k` (default 8 → prova 10-15)
3. Modifica `DIRETTIVA_PROMPT`: `POST /save_parameters`
4. Verifica qualità documenti nel Chroma: `GET /debug_db/`
5. Prova reindex con diversi parametri di chunking

### Problema: Streaming bloccato / non funziona
**Soluzione:**
- Verifica che client supporti streaming (Content-Type: text/plain)
- Usa `curl -N` per disabilitare buffering
- Prova con Python: 
  ```python
  import httpx
  with httpx.stream("POST", "http://localhost:8000/chat/stream", ...) as r:
    for chunk in r.iter_text():
        print(chunk, end="", flush=True)
  ```
- Verifica che server sia in ascolto: `netstat -ano | grep 8000`

### Problema: Modelli Ollama non si scaricano
**Soluzione:**
```bash
# Verifica manualmente
ollama pull mistral:latest

# Check disponibili
ollama list

# Se errore di rete: verifica proxy/firewall
# Configura Ollama per HTTP proxy se necessario
```

---

## 📝 Licenza

Questo progetto è interno per studi legali. Non distribuire senza autorizzazione.

---

**Documento aggiornato:** December 16, 2025  
**Versione:** 1.1 (Dynamic Chunking, Streaming, Model Management)  
**Branch:** RAGIS_v1.0  

### Novità v1.1
- ✅ Dynamic Chunking implementato (DynamicChunker a 4 livelli)
- ✅ Streaming responses (`/chat/stream`)
- ✅ Gestione modelli LLM (`/get_models`, `/download_model`)
- ✅ DIRETTIVA_PROMPT configurabile
- ✅ Override modello per singola query (ChatRequest.llm_model)
- ✅ Reindex automatico con chunking dinamico
- ✅ Parametri system persistenti in DB
