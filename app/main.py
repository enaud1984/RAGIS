# ==========================================
# Legal RAG Backend (Ollama version)
# ==========================================
# Requisiti:
# pip install fastapi uvicorn langchain chromadb unstructured pdfminer.six python-docx
# ollama pull llama3
# ==========================================

import os
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.chat_models import ChatOllama
from langchain_community.document_loaders import Docx2txtLoader,DirectoryLoader, Docx2txtLoader, PyPDFLoader, UnstructuredFileLoader
import hashlib
# =============================
# CONFIGURAZIONE
# =============================

DATA_DIR = "../Documenti"
DB_DIR = "data/chroma_db"
# Modello LLM per risposte (piccolo e CPU-friendly)
LLM_MODEL = "gemma:2b"

# Modello per embeddings (specifico per vettori)
EMBED_MODEL = "nomic-embed-text"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)

# =============================
# FUNZIONI RAG
# =============================

def get_file_hash(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def build_vector_db():
    """
    Indicizza solo i nuovi documenti non ancora presenti nel DB.
    """
    print("📚 Indicizzazione incrementale in corso...")

    embeddings = OllamaEmbeddings(model=EMBED_MODEL)
    vectordb = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)

    # Recupera file già indicizzati (metadati)
    existing_docs = vectordb.get()
    existing_hashes = {m["hash"] for m in existing_docs["metadatas"] if "hash" in m}

    def smart_loader(path):
        if path.endswith(".pdf"):
            return PyPDFLoader(path)
        elif path.endswith(".docx"):
            return Docx2txtLoader(path)
        else:
            return UnstructuredFileLoader(path)

    loader = DirectoryLoader(DATA_DIR, glob="**/*.*", loader_cls=smart_loader)
    all_docs = loader.load()

    new_docs = []
    for doc in all_docs:
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

    print(f"✅ Indicizzati {len(new_docs)} nuovi documenti.")
    return {"message": f"Indicizzati {len(new_docs)} nuovi documenti."}



def get_vector_db():
    """
    Carica il database vettoriale esistente.
    """
    embeddings = OllamaEmbeddings(model=EMBED_MODEL)
    vectordb = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
    return vectordb


def query_rag(question: str):
    """
    Esegue la ricerca semantica e genera la risposta tramite LLM (Ollama).
    """
    vectordb = get_vector_db()
    results = vectordb.similarity_search(question, k=3)
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
