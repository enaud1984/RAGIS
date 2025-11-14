# ==========================================
# Legal RAG Backend (Ollama version)
# ==========================================
# Requisiti:
# pip install fastapi uvicorn langchain chromadb unstructured pdfminer.six python-docx
# ollama pull llama3
# ==========================================
import glob
import os
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_community.chat_models import ChatOllama
from langchain_unstructured import UnstructuredLoader
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
    UnstructuredEmailLoader,
    DirectoryLoader,
    UnstructuredExcelLoader
)

import hashlib


os.environ["UNSTRUCTURED_DISABLE_ANALYTICS"] = "true"
os.environ["DO_NOT_TRACK"] = "true"
# =============================
# CONFIGURAZIONE
# =============================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "../Documenti"))
print(f"📁 Sto leggendo i file da: {DATA_DIR}")
DB_DIR = os.path.join(BASE_DIR, "data", "chroma_db")
# Modello LLM per risposte (piccolo e CPU-friendly)
LLM_MODEL = "gemma:2b"

# Modello per embeddings (specifico per vettori)
EMBED_MODEL = "nomic-embed-text"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)
EMBEDDINGS = OllamaEmbeddings(model=EMBED_MODEL)
# =============================
# FUNZIONI RAG
# =============================

def get_file_hash(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def smart_loader(path: str):
    ext = os.path.splitext(path)[1].lower()

    if ext == ".pdf":
        return PyPDFLoader(path)
    elif ext in (".doc", ".docx"):
        return Docx2txtLoader(path)
    elif ext == ".txt":
        return TextLoader(path, encoding="utf-8")
    elif ext == ".eml":
        return UnstructuredEmailLoader(path)
    elif ext in (".xls", ".xlsx"):
        return UnstructuredExcelLoader(path)
    else:
        return UnstructuredLoader(path)


def load_all_documents(base_dir: str):
    """
    Sostituisce DirectoryLoader con gestione dinamica del loader.
    """
    docs = []
    excluded_exts = (".md", ".csv", ".png", ".jpg", ".jpeg")

    for path in glob.glob(os.path.join(base_dir, "**/*.*"), recursive=True):
        if path.lower().endswith(excluded_exts):
            continue
        try:
            loader = smart_loader(path)
            subdocs = loader.load()
            docs.extend(subdocs)
            print(f"📄 Caricato: {os.path.basename(path)} ({len(subdocs)} parti)")
        except Exception as e:
            print(f"⚠️ Errore caricando {path}: {e}")
    return docs

def build_vector_db():
    """
    Indicizza solo i nuovi documenti non ancora presenti nel DB,
    ignorando i file non utili come .md, .csv, ecc.
    """
    print("📚 Indicizzazione incrementale in corso...")

    vectordb = Chroma(persist_directory=DB_DIR, embedding_function=EMBEDDINGS)

    # Recupera file già indicizzati (metadati)
    existing_docs = vectordb.get()
    existing_hashes = {m["hash"] for m in existing_docs["metadatas"] if "hash" in m}

    all_docs = load_all_documents(DATA_DIR)

    # 🔹 Filtra i file non desiderati (.md, .csv, ecc.)
    excluded_exts = (".md", ".csv", ".png", ".jpg", ".jpeg")
    valid_docs = [
        d for d in all_docs
        if not d.metadata.get("source", "").lower().endswith(excluded_exts)
    ]

    new_docs = []
    for doc in valid_docs:
        file_path = doc.metadata["source"]
        file_hash = get_file_hash(file_path)
        if file_hash not in existing_hashes:
            doc.metadata["hash"] = file_hash
            new_docs.append(doc)

    if not new_docs:
        print("✅ Nessun nuovo documento da indicizzare.")
        return {"message": "Nessun nuovo documento."}

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = splitter.split_documents(new_docs)

    vectordb.add_documents(chunks)
    vectordb.persist()

    print(f"✅ Indicizzati {len(new_docs)} nuovi documenti validi.")
    return {"message": f"Indicizzati {len(new_docs)} nuovi documenti validi."}


def get_vector_db():
    print(f"🧭 Carico il DB da: {DB_DIR}")
    vectordb = Chroma(persist_directory=DB_DIR, embedding_function=EMBEDDINGS)
    return vectordb


def query_rag(question: str):
    """
    Esegue la ricerca semantica e genera la risposta tramite LLM (Ollama).
    """
    vectordb = get_vector_db()
    results = vectordb.similarity_search(question, k=10)
    print(results)
    print(f"🔍 Trovati {len(results)} documenti rilevanti")
    context = "\n\n".join([doc.page_content for doc in results])

    # TODO: aggiungere in futuro fonti esterne (es. banche dati legali online)
    llm = ChatOllama(model=LLM_MODEL, temperature=0)
    prompt = f"""Sei un assistente legale esperto. 
Usa SOLO il seguente contesto per rispondere alla domanda.
Se la risposta non è nel contesto, di' che non ci sono informazioni sufficienti.

Domanda: {question}

Contesto disponibile:
{context}

Risposta:"""

    response = llm.invoke(prompt)
    return response.content


# =============================
# API FASTAPI
# =============================

app = FastAPI(title="Legal RAG Backend (Ollama)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/chat/")
def chat(prompt: str = Body(..., embed=True)):
    """
    Endpoint principale della chat.
    """
    try:
        answer = query_rag(prompt)
        return {"answer": answer}
    except Exception as e:
        return {"error": str(e)}


@app.get("/reindex/")
def reindex():
    """
    Ricostruisce il database vettoriale da zero (per nuovi documenti).
    """
    try:
        build_vector_db()
        return {"message": "Indicizzazione completata con successo."}
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug_db/")
def debug_db():
    vectordb = get_vector_db()
    all_data = vectordb.get()
    num_docs = len(all_data["ids"])
    print(f"📊 Documenti totali nel DB: {num_docs}")
    return {"documenti": num_docs, "metadati": all_data["metadatas"][:3]}


@app.get("/")
def root():
    return {"message": "Legal RAG Backend (Ollama) attivo. Usa /chat o /reindex"}


# =============================
# ESECUZIONE SERVER
# =============================

if __name__ == "__main__":
    import uvicorn
    print("🚀 Avvio Legal RAG (Ollama) su http://127.0.0.1:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
