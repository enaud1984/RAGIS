import asyncio
from typing import Tuple, Any, AsyncGenerator

from langchain_ollama import ChatOllama
from starlette.requests import Request

from settings import *
from rag.embeddings import get_vector_db
from logger_ragis.rag_log import RagLog

log = RagLog.get_logger("rag_query")

def decide_from_db(request:Request,prompt: str, threshold: float = 0.7, top_k: int = 10) -> Tuple[bool, str]:
    vectordb = get_vector_db(request)

    # 1) Prompt troppo breve → niente RAG
    #if len(prompt.split()) < 4:
    #    return False, "Prompt troppo breve per una ricerca affidabile."

    # 2) Threshold dinamico
    if len(prompt.split()) < 6:
        threshold = min(threshold, 0.35)

    results = vectordb.similarity_search_with_score(prompt, k=top_k)
    if not results:
        return False, "DB vuoto o nessun match."

    # Ordina per distanza
    results.sort(key=lambda x: x[1])

    # 3) Richiedi almeno 2 match forti
    close_matches = [(doc, dist) for doc, dist in results if dist <= threshold]

    if len(close_matches) < 2:
        return False, "Match insufficienti per usare il RAG."

    return True, "Match soddisfacenti nei documenti."


def query_rag(request:Request, question: str, top_k: int = None, distance_threshold: float = None,llm_model:str=None) -> Tuple[str, List[Dict[str, str]]]:
    log.info("Prompt: %s", question)
    params = request.app.state.params

    top_k = top_k or params["top_k"]
    distance_threshold = distance_threshold or params["distance_threshold"]
    llm_model = llm_model or params["llm_model"]

    vectordb = get_vector_db(request)
    results = vectordb.similarity_search_with_score(question, k=top_k)
    if not results:
        raise RuntimeError("Nessun risultato dalla ricerca vettoriale.")

    # filtra e ordina
    results = sorted(results, key=lambda x: x[1])
    filtered = [(doc, dist) for (doc, dist) in results if dist <= distance_threshold]

    if not filtered:
        return "", []

    # costruisco contesto limitato (es. primi 5 chunk)
    max_chunks = 5

    context_parts = []
    sources = []

    # Costruzione contesto documenti
    for i, (doc, dist) in enumerate(filtered[:max_chunks]):
        snippet = doc.page_content.strip()
        src = doc.metadata.get('source')
        idx = doc.metadata.get("chunk_index", "-")
        context_parts.append(
            f"📄 Fonte: {src} | Chunk: {idx} | Distanza: {dist:.3f}\n{snippet}"
        )
        sources.append({
            "source": src,
            "distance": f"{dist:.3f}",
            "chunk_index": str(idx)
        })

    # Se nessun documento è rilevante
    if context_parts:
        context = "\n\n---\n\n".join(context_parts)
    else:
        context = ""  # CONTENUTO VUOTO = non costringiamo il modello a usarlo

    # Recupero direttiva dal DB
    db = ParameterDB()
    system_prompt = db.get("DIRETTIVA_PROMPT")

    full_prompt = f"""
    {system_prompt}

    CONTESTO (usalo SOLO se pertinente):
    {context if context else "Nessun contesto rilevante trovato."}

    DOMANDA DELL'UTENTE:
    {question}
    """

    llm = ChatOllama(model=llm_model, temperature=0)
    resp = llm.invoke(full_prompt)
    answer_text = getattr(resp, "content", str(resp))

    return answer_text, sources

async def query_rag_stream(request:Request,
                     question: str,
                     top_k: int = None,
                     distance_threshold: float = None,
                     llm_model:str=None) -> AsyncGenerator[str, Any]:
    """
        Versione streaming di query_rag.
        Produce token/chunk incrementali ed è interrompibile.
    """

    log.info("Prompt: %s", question)

    params = request.app.state.params

    top_k = top_k or params["top_k"]
    distance_threshold = distance_threshold or params["distance_threshold"]
    llm_model = llm_model or params["llm_model"]

    vectordb = get_vector_db(request)
    results = vectordb.similarity_search_with_score(question, k=top_k)
    if not results:
        yield "Nessun risultato dalla ricerca vettoriale."
        return

    # filtra e ordina
    results = sorted(results, key=lambda x: x[1])
    filtered = [(doc, dist) for (doc, dist) in results if dist <= distance_threshold]

    if not filtered:
        yield "Non ho trovato informazioni rilevanti nei documenti."
        return

    # costruisco contesto limitato (es. primi 5 chunk)
    max_chunks = 5

    context_parts = []
    sources = []

    # Costruzione contesto documenti
    for i, (doc, dist) in enumerate(filtered[:max_chunks]):
        snippet = doc.page_content.strip()
        src = doc.metadata.get('source')
        idx = doc.metadata.get("chunk_index", "-")
        context_parts.append(
            f"📄 Fonte: {src} | Chunk: {idx} | Distanza: {dist:.3f}\n{snippet}"
        )
        sources.append({
            "source": src,
            "distance": f"{dist:.3f}",
            "chunk_index": str(idx)
        })

    # Se nessun documento è rilevante
    if context_parts:
        context = "\n\n---\n\n".join(context_parts)
    else:
        context = ""  # CONTENUTO VUOTO = non costringiamo il modello a usarlo

    # Recupero direttiva dal DB
    db = ParameterDB()
    system_prompt = db.get("DIRETTIVA_PROMPT")

    full_prompt = f"""
    {system_prompt}

    CONTESTO (usalo SOLO se pertinente):
    {context if context else "Nessun contesto rilevante trovato."}

    DOMANDA DELL'UTENTE:
    {question}
    """

    llm = ChatOllama(model=llm_model, temperature=0)
    try:
        async for chunk in llm.astream([("human", full_prompt)]):
            # chunk è un AIMessageChunk
            if chunk.content:
                yield chunk.content
            await asyncio.sleep(0)
    except Exception as e:
        yield f"Errore durante la generazione della risposta: {e}"
        return

    if sources:
        yield "\n\n---\nFONTI:\n"
        for s in sources:
            yield f"- {s['source']} (chunk {s['chunk_index']}, dist={s['distance']})\n"
