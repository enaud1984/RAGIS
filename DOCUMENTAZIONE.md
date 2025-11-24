# 📚 RAGIS - Documentazione Completa

## 📖 Indice
1. [Panoramica Generale](#panoramica-generale)
2. [Architettura del Sistema](#architettura-del-sistema)
3. [Flusso Tecnico](#flusso-tecnico)
4. [Moduli Principali](#moduli-principali)
5. [API Endpoints](#api-endpoints)
6. [Database](#database)
7. [Autenticazione e Autorizzazione](#autenticazione-e-autorizzazione)
8. [Configurazione](#configurazione)
9. [Guida All'Uso](#guida-alluso)

---

## 🎯 Panoramica Generale

**RAGIS** è un sistema **Retrieval-Augmented Generation (RAG)** per studi legali italiani. Permette di:

- 📤 **Caricare documenti** (PDF, Word, Email, Excel, TXT)
- 🔍 **Indicizzare** i documenti in un database vettoriale (Chroma)
- 💬 **Interrogare** il sistema tramite chatbot intelligente
- 👥 **Gestire utenti** con differenti ruoli (admin, user)
- ⚙️ **Configurare parametri** dinamicamente
- 🔐 **Autenticare** tramite JWT

**Stack tecnologico:**
- Backend: FastAPI (Python)
- LLM: Ollama (modelli locali)
- Embeddings: HuggingFace
- VectorDB: ChromaDB
- Database: SQLite
- Frontend: React.js

---

## 🏗️ Architettura del Sistema

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
│  │  Endpoints:                                        │ │
│  │  • POST /chat/ → Query RAG                        │ │
│  │  • POST /upload/ → Upload documenti                │ │
│  │  • GET /reindex/ → Reindex manuale                │ │
│  │  • POST /login → Autenticazione                    │ │
│  │  • POST /registrazione → Registra utente           │ │
│  │  • GET /lista-utenti → Lista utenti (admin)        │ │
│  │  • PUT /aggiorna-utente → Modifica utente          │ │
│  │  • DELETE /cancella-utente → Cancella utente       │ │
│  │  • GET /debug_db/ → Debug vettoriale               │ │
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌────────────────────┐  ┌───────────────┐
│  Autenticazione │  │  RAG Processing    │  │    Database   │
│   (auth.py)     │  │   (rag/module)      │  │  (db_sql/)    │
│                 │  │                    │  │               │
│ • JWT           │  │ • embeddings.py    │  │ • SQLite      │
│ • BCrypt        │  │ • indexing.py      │  │ • Users table │
│ • Password Hash │  │ • loaders.py       │  │ • Params      │
└─────────────────┘  │ • rag_query.py     │  └───────────────┘
                     │                    │
                     └────────────────────┘
                              │
                     ┌────────┴──────────┐
                     ▼                   ▼
            ┌─────────────────┐  ┌──────────────────┐
            │  Chroma Vector  │  │  Documenti       │
            │  Database       │  │  (Documenti/)    │
            │                 │  │                  │
            │ data/chroma_db/ │  │ • PDF            │
            │ (Embeddings)    │  │ • Word (.docx)   │
            └─────────────────┘  │ • Email (.eml)   │
                                 │ • Excel (.xlsx)  │
                                 │ • TXT            │
                                 └──────────────────┘
                                          │
                                 ┌────────┴──────────┐
                                 ▼                   ▼
                        ┌─────────────────┐  ┌──────────────┐
                        │   Ollama LLM    │  │ HuggingFace  │
                        │  (mistral/...)  │  │ Embeddings   │
                        │  Modello locale │  │ (e5-large)   │
                        └─────────────────┘  └──────────────┘
```

---

## 🔄 Flusso Tecnico

### Flusso 1: Caricamento e Indicizzazione Documenti

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
│ GET /reindex/ (manuale)      │
│ O Crontab 03:00 (notturno)   │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ build_vector_db()            │
│ (indexing.py)                │
│                              │
│ 1. Carica tutti i documenti  │
│ 2. Filtra estensioni         │
│ 3. Calcola hash file (dedup) │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ load_all_documents()         │
│ (loaders.py)                 │
│                              │
│ Smart loader per tipo:       │
│ • .pdf → PyPDFLoader         │
│ • .docx → Unstructured       │
│ • .eml → UnstructuredEmail   │
│ • .xlsx → UnstructuredExcel  │
│ • .txt → TextLoader          │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ RecursiveCharacterSplitter   │
│ Divide documenti in chunks:  │
│ • chunk_size: 1500 chars     │
│ • chunk_overlap: 200 chars   │
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
│ con metadati (source, hash)  │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ ✅ Reindex completato        │
│ DB vettoriale aggiornato     │
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
| `@app.post("/upload/")` | Upload documenti (admin) |
| `@app.post("/login")` | Autenticazione utente |
| `@app.post("/registrazione")` | Registra nuovo utente (admin) |
| `@app.get("/lista-utenti")` | Lista utenti (admin) |
| `@app.put("/aggiorna-utente")` | Modifica utente (admin) |
| `@app.delete("/cancella-utente")` | Cancella utente (admin) |
| `@app.get("/reindex/")` | Reindex manuale (admin) |
| `@app.get("/debug_db/")` | Debug vettoriale |

#### Middleware:
- **CORS**: Permette richieste da qualsiasi origine
- **Reindexing Check**: Blocca API durante reindex

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
- Caricamento parametri da DB
- Configurazione percorsi directory

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

class ChatResponse:
    answer: str
    sources: List[Dict[str, str]] = []
```

#### Funzione `resolve_params()`:
Legge da DB (ParameterDB) tutti i parametri di configurazione:
- `llm_model` (default: "mistral")
- `embed_model` (default: "intfloat/e5-large-v2")
- `chunk_size` (default: 1500)
- `chunk_overlap` (default: 200)
- `top_k` (default: 8)
- `distance_threshold` (default: 0.6)
- `excluded_exts` (default: ".md,.csv,.png,.jpg,.jpeg")
- `cron_reindex` (default: "0 3 * * *" → 03:00 ogni giorno)
- `data_dir` (default: "Documenti")

---

### 4. **rag/embeddings.py** - Gestione Embeddings e Vector DB

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

### 5. **rag/loaders.py** - Caricamento Documenti

#### Responsabilità:
- Supporto multiple formato file
- Hash file per deduplicazione
- Gestione errori caricamento

#### Funzioni:

| Funzione | Input | Output |
|----------|-------|--------|
| `load_all_documents(base_dir)` | Path dir | List[Document] |
| `smart_loader(path)` | Path file | Loader istanza |
| `get_file_hash(path)` | Path file | MD5 hexdigest |

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

### 6. **rag/indexing.py** - Indicizzazione Vettoriale

#### Responsabilità:
- Deduplicazione documenti (per hash)
- Chunking con overlap
- Aggiunta chunk a Chroma

#### Funzione: `build_vector_db()`

**Passi:**
1. Legge metadati esistenti da Chroma
2. Carica tutti documenti da `data_dir`
3. Filtra per estensioni escluse
4. Calcola hash file
5. Mantiene solo nuovi documenti (dedup)
6. Divide in chunk (RecursiveCharacterTextSplitter)
7. Genera ID univoci (`{hash}-{chunk_index}`)
8. Salva in Chroma con metadati

**Deduplicazione:** Se un file ha hash identico a uno già indicizzato, viene saltato.

---

### 7. **rag/rag_query.py** - Query e Generazione Risposta

#### Responsabilità:
- Decisione uso RAG (threshold matching)
- Query similarità vettoriale
- Generazione risposta con LLM

#### Funzioni:

##### `decide_from_db(prompt, threshold, top_k)`
**Logica:**
1. Se prompt < 4 parole → No RAG
2. Se prompt < 6 parole → threshold = min(threshold, 0.35)
3. Ricerca similarità top_k
4. Filtra per threshold
5. Ritorna True se ≥2 match forti

##### `query_rag(question, top_k, distance_threshold)`
**Logica:**
1. Ricerca similarità con embedding question
2. Filtra per distance_threshold
3. Seleziona max 5 chunk
4. Costruisce contesto in formato:
   ```
   Fonte: {file} (distanza: {score})
   {snippet}
   
   ---
   
   Fonte: {file2} (distanza: {score2})
   {snippet2}
   ```
5. Invoca ChatOllama con:
   - System prompt: "Sei un assistente legale italiano..."
   - Context: chunk filtrati
   - Question: domanda utente
   - Temperature: 0 (deterministico)
6. Ritorna: (answer_text, sources_metadata)

**Sources Metadata:**
```python
{
  "source": "Documenti/Clients/Bianchi_SRL/Correspondence/notifica_1.eml",
  "distance": "0.234",
  "chunk_index": "2"
}
```

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

### Chat (Protetto)

#### `POST /chat/`
**Query RAG principale**

Headers: `Authorization: Bearer {JWT}`

Request:
```json
{
  "prompt": "Quali sono i termini di pagamento secondo la notifica ricevuta?",
  "top_k": 5,
  "distance_threshold": 0.6
}
```

Response:
```json
{
  "answer": "Secondo la notifica ricevuta, i termini di pagamento sono...",
  "sources": [
    {
      "source": "Documenti/Clients/Bianchi_SRL/Correspondence/notifica_1.eml",
      "distance": "0.234",
      "chunk_index": "2"
    }
  ]
}
```

Status: `200 OK` | `401 Unauthorized` | `400 Bad Request`

**Logica:**
- Se reindexing → ritorna messaggio temporaneo
- Se prompt vuoto → 400
- Se nessun match → risposta negativa
- Se match insufficienti → risposta suggeritoria

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
**Reindex manuale database vettoriale**

Headers: `Authorization: Bearer {JWT}`

Response:
```json
{
  "message": "Indicizzati 3 nuovi documenti (tot chunk: 45)."
}
```

Status: `200 OK` | `500 Internal Server Error`

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

### Parametri (Protetto - Admin)

#### `POST /save_parameters`
**Salva parametri configurazione**

Headers: `Authorization: Bearer {JWT}`

Request:
```json
{
  "llm_model": "llama2",
  "top_k": "10",
  "distance_threshold": "0.5"
}
```

Response: `200 OK`

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

# Directory database Chroma
DB_DIR=/path/to/RAGIS/data/chroma_db
```

### Parametri Configurabili (Database)

**Query in Python:**
```python
from database.parameter_db import ParameterDB

db = ParameterDB()

# Lettura
model = db.get("llm_model", "mistral")

# Scrittura
db.set("llm_model", "llama2", tipo="string", descrizione="Modello LLM")
```

### File Configurazione

**`requirements.txt`:** Dipendenze Python

**`Documenti/`:** Directory documenti di input

**`data/chroma_db/`:** Vector database persistente

**`db_sql/app.db`:** Database SQLite

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

### Workflow Tipico

#### 1. Admin carica documenti
- Login come `admin`
- POST `/upload/` con file
- File salvati in `Documenti/`

#### 2. Sistema indicizza (automatico o manuale)
- **Automatico:** Crontab 03:00 ogni giorno
- **Manuale:** Admin chiama GET `/reindex/`
- Documenti convertiti in chunk e embedding

#### 3. User fa domanda
- Login (user o admin)
- POST `/chat/` con domanda
- Sistema ricerca chunk simili
- LLM genera risposta con fonti

#### 4. Admin gestisce utenti
- POST `/registrazione/` → crea nuovi user
- PUT `/aggiorna-utente/{id}` → modifica
- DELETE `/cancella-utente/{id}` → cancella

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

### Esempio 1: Registrazione nuovo utente

```bash
# Admin login
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Ragis@2025Admin"}'

# Risposta: {"token":"eyJhbGc...","username":"admin","ruolo":"admin"}

# Registra nuovo user con token
curl -X POST http://localhost:8000/registrazione \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGc..." \
  -d '{
    "username":"mario_rossi",
    "password":"Password123",
    "ruolo":"user"
  }'
```

### Esempio 2: Upload documento e query

```bash
# Upload file
curl -X POST http://localhost:8000/upload/ \
  -H "Authorization: Bearer <token>" \
  -F "files=@notifica.eml"

# Manual reindex
curl -X GET http://localhost:8000/reindex/ \
  -H "Authorization: Bearer <token>"

# Query RAG
curl -X POST http://localhost:8000/chat/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Quali sono i termini di pagamento?",
    "top_k": 5,
    "distance_threshold": 0.6
  }'
```

### Esempio 3: Modifica parametri

```python
from database.parameter_db import ParameterDB

db = ParameterDB()

# Cambio modello LLM
db.set("llm_model", "llama2", tipo="string", descrizione="Modello LLM")

# Cambio soglia similarità
db.set("distance_threshold", "0.5", tipo="decimal", descrizione="Soglia")

# Cambio top_k
db.set("top_k", "10", tipo="number", descrizione="Top K chunk")
```

---

## 🐛 Troubleshooting

### Problema: "Ollama not available"
**Soluzione:** Assicurati che `ollama serve` sia in esecuzione in background

### Problema: "Token scaduto"
**Soluzione:** Login di nuovo per ottenere nuovo JWT (TTL: 12 ore)

### Problema: "Nessun documento trovato"
**Soluzione:** 
1. Verifica che file siano in `Documenti/`
2. Controlla che non siano in estensioni escluse
3. Esegui reindex manuale: GET `/reindex/`

### Problema: "Database locked"
**Soluzione:** SQLite a volte ha contention; riavvia server

### Problema: Risposte LLM off-topic
**Soluzione:** 
- Abbassa `distance_threshold` (più permissivo)
- Aumenta `top_k` (più chunk nel contesto)
- Modifica system prompt in `rag_query.py`

---

## 📝 Licenza

Questo progetto è interno per studi legali. Non distribuire senza autorizzazione.

---

**Documento generato:** November 24, 2025  
**Versione:** 1.0  
**Branch:** RAGIS_v1.0
