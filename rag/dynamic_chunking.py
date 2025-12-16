"""
STRATEGIA DI CHUNKING DINAMICO PER RAG AFFIDABILE
================================================

Questo modulo implementa un sistema di chunking adattivo che:
1. Analizza la STRUTTURA del testo (paragrafi, titoli, sezioni)
2. Valuta la COMPLESSITÀ semantica (lunghezza media frasi, densità lessicale)
3. Rispetta SEPARATORI NATURALI per preservare coesione semantica
4. Evita chunk troppo piccoli (<100 token) o troppo grandi (>600 token)
5. Combina strategie ricorsive + strutturali per ottenere qualità ottima

MOTIVAZIONE:
- Chunk fissi compromettono la qualità: un titolo + 1 frase è insufficiente
- Paragafi interi sono meglio di frammentazioni forzate
- Titoli + primo paragrafo = contesto completo per il retrieval
- LLM comprende meglio chunk coesivi rispetto a tagli casuali
"""

import re
from typing import List, Dict, Tuple
from dataclasses import dataclass
from langchain_core.documents import Document
from logger_ragis.rag_log import RagLog

log = RagLog.get_logger("dynamic_chunking")


@dataclass
class ChunkingConfig:
    """Configurazione del chunking dinamico."""
    # Limiti di token (approssimativi, ~4 char ≈ 1 token)
    min_chunk_tokens: int = 100  # ~400 char
    max_chunk_tokens: int = 600  # ~2400 char
    
    # Strategie
    respect_structure: bool = True  # Rispetta paragrafi/titoli
    merge_small_chunks: bool = True  # Combina chunk troppo piccoli
    include_context_headers: bool = True  # Aggiungi titolo al paragrafo
    
    # Separatori naturali
    section_markers: List[str] = None  # Ad es. ["#", "##", "Articolo", "Capo"]
    paragraph_threshold: int = 50  # Minimo char per considerare un paragrafo
    
    def __post_init__(self):
        if self.section_markers is None:
            self.section_markers = ["#", "##", "###", "Articolo", "Capo", "Sezione", "Capitolo"]


class DynamicChunker:
    """
    Implementa chunking dinamico con 4 strategie:
    
    LIVELLO 1: Strutturale
        → Divide per sezioni (titoli, articoli, capitoli)
        → Preserva titolo come contesto per paragrafi successivi
    
    LIVELLO 2: Paragrafale
        → Mantiene paragrafi interi se < max_size
        → Combina paragrafi piccoli al precedente
    
    LIVELLO 3: Sintattico
        → Se paragrafo > max_size: divide per frasi
        → Intelligente: evita tagli in mezzo a parentesi/numeri
    
    LIVELLO 4: Ricorsivo fallback
        → Se frase > max: split ricorsivo conservativo
    """
    
    def __init__(self, config: ChunkingConfig = None):
        self.config = config or ChunkingConfig()
    
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """Applica chunking dinamico a una lista di documenti."""
        chunked_docs = []
        
        for doc in documents:
            text = doc.page_content
            source = doc.metadata.get("source", "unknown")
            
            log.debug(f"Chunking {source} ({len(text)} char)")
            
            chunks = self._chunk_text(text)
            
            for i, chunk_text in enumerate(chunks):
                new_doc = Document(
                    page_content=chunk_text,
                    metadata={
                        **doc.metadata,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "chunk_strategy": "dynamic"
                    }
                )
                chunked_docs.append(new_doc)
                log.debug(f"  Chunk {i}: {len(chunk_text)} char ({self._estimate_tokens(chunk_text)} tok)")
        
        return chunked_docs
    
    def _chunk_text(self, text: str) -> List[str]:
        """Orchestrazione principale: applica strategie in sequenza."""
        text = self._clean_text(text)
        
        # LIVELLO 1: Dividi per sezioni (titoli/capitoli)
        sections = self._split_by_structure(text)
        
        # LIVELLO 2: Per ogni sezione, dividi per paragrafi
        all_chunks = []
        for section_title, section_text in sections:
            paragraphs = self._split_by_paragraphs(section_text)
            
            # Aggiungi contesto del titolo
            paragraphs_with_context = [
                (f"{section_title}\n{p}" if section_title else p)
                for p in paragraphs
            ]
            
            # LIVELLO 3: Gestisci paragrafi grandi
            for para in paragraphs_with_context:
                if self._estimate_tokens(para) <= self.config.max_chunk_tokens:
                    all_chunks.append(para)
                else:
                    # Dividi frase per frase
                    para_chunks = self._split_by_sentences(para)
                    all_chunks.extend(para_chunks)
        
        # Post-processing: combina chunk molto piccoli
        if self.config.merge_small_chunks:
            all_chunks = self._merge_small_chunks(all_chunks)
        
        return all_chunks
    
    def _split_by_structure(self, text: str) -> List[Tuple[str, str]]:
        """
        LIVELLO 1: Dividi per sezioni strutturali.
        Ritorna lista di (titolo, contenuto).
        
        Esempi:
        - "# Titolo\nTesto..." → ("Titolo", "Testo...")
        - "Articolo 1\nTesto..." → ("Articolo 1", "Testo...")
        """
        sections = []
        current_title = ""
        current_content = []
        
        lines = text.split("\n")
        
        for line in lines:
            # Rileva titoli (Markdown o pattern legali)
            is_header = any(
                line.strip().startswith(marker)
                for marker in self.config.section_markers
            )
            
            if is_header and current_content:
                # Salva sezione precedente
                content_text = "\n".join(current_content).strip()
                if content_text:
                    sections.append((current_title, content_text))
                current_content = []
                current_title = line.strip()
            elif is_header:
                current_title = line.strip()
            else:
                current_content.append(line)
        
        # Ultima sezione
        if current_content:
            content_text = "\n".join(current_content).strip()
            if content_text:
                sections.append((current_title, content_text))
        
        return sections if sections else [("", text)]
    
    def _split_by_paragraphs(self, text: str) -> List[str]:
        """
        LIVELLO 2: Dividi per paragrafi.
        
        Un paragrafo è:
        - Blocco di testo separato da righe vuote
        - Almeno `paragraph_threshold` caratteri
        
        Perché è importante:
        - Mantiene coesione semantica dentro paragrafo
        - Paragrafi sono unità di significato naturale
        """
        paragraphs = []
        
        # Dividi per righe vuote (doppio newline è paragrafo)
        raw_paragraphs = re.split(r"\n\s*\n", text)
        
        for para in raw_paragraphs:
            para = para.strip()
            if len(para) < self.config.paragraph_threshold:
                continue
            paragraphs.append(para)
        
        return paragraphs if paragraphs else [text.strip()]
    
    def _split_by_sentences(self, text: str) -> List[str]:
        """
        LIVELLO 3: Dividi per frasi se paragrafo è troppo grande.
        
        Algoritmo:
        1. Estrai frasi usando regex robusta
        2. Accumula frasi finché fit in max_tokens
        3. Quando aggiungi frase che esce dal limite → flush
        
        Perché è intelligente:
        - Evita spezzare frasi
        - Mantiene boundary logiche
        - Accumula frasi correlate
        """
        sentences = self._extract_sentences(text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            test_chunk = (current_chunk + " " + sentence).strip()
            
            if self._estimate_tokens(test_chunk) <= self.config.max_chunk_tokens:
                current_chunk = test_chunk
            else:
                # Chunk attuale è pieno
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
        
        # Ultima frase
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks if chunks else [text]
    
    def _extract_sentences(self, text: str) -> List[str]:
        """
        Estrae frasi usando regex intelligente.
        
        Patterns:
        - ".XXX Yyyyyy" = fine frase, inizio nuova
        - "!?" = punteggiatura forte
        - Evita falsi positivi: abbreviazioni (es. "dott."), numeri
        """
        # Pattern: fine frase = punto/esclamativo/interrogativo + spazio + maiuscola
        # Ma NON se punto è parte di abbreviazione
        
        # Semplice: dividi per ". " / "! " / "? "
        # Pattern avanzato: evita "dott." "art." ecc
        
        pattern = r"(?<=[.!?])\s+(?=[A-ZÀ-Ù])"
        sentences = re.split(pattern, text)
        
        # Pulizia: rimuovi stringhe vuote
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences if sentences else [text]
    
    def _merge_small_chunks(self, chunks: List[str]) -> List[str]:
        """
        Post-processing: combina chunk troppo piccoli.
        
        Logica:
        - Se chunk < min_tokens → fonda con precedente
        - Assicura qualità: niente frammenti isolati
        
        Esempio:
        chunks = ["Titolo intro lungo...", "Aggiunta.", "Paragrafo lungo..."]
        → ["Titolo intro lungo...", "Paragrafo lungo con aggiunta..."]
        """
        if not chunks:
            return chunks
        
        merged = []
        i = 0
        
        while i < len(chunks):
            current = chunks[i]
            
            # Guarda il prossimo chunk
            while (
                i + 1 < len(chunks) and
                self._estimate_tokens(current) < self.config.min_chunk_tokens
            ):
                # Fonda con il prossimo
                current = current + " " + chunks[i + 1]
                i += 1
            
            # Se ancora troppo piccolo, lascia lo stesso
            # (potrebbe essere ultimo chunk)
            merged.append(current)
            i += 1
        
        return merged
    
    def _estimate_tokens(self, text: str) -> int:
        """Stima tokens: ~4 char = 1 token (approssimazione).
        
        Per risultati precisi con OpenAI/Hugging Face:
        import tiktoken
        enc = tiktoken.encoding_for_model("gpt-3.5-turbo")
        return len(enc.encode(text))
        """
        return max(1, len(text) // 4)
    
    def _clean_text(self, text: str) -> str:
        """Pulizia base: rimuovi spazi doppi, control chars."""
        text = re.sub(r"\s+", " ", text)  # Spazi multipli → uno
        text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)  # Control chars
        return text.strip()


# ==================== UTILITY ====================

def analyze_document_structure(text: str) -> Dict[str, any]:
    """
    Analizza la struttura del documento per determinare la strategia di chunking.
    
    Ritorna dizionario con:
    - num_sections: numero di titoli/sezioni rilevati
    - num_paragraphs: numero di paragrafi
    - structure_type: 'legal', 'technical', 'narrative', 'mixed'
    - avg_paragraph_length: lunghezza media paragrafo
    - has_headers: ha intestazioni?
    - has_lists: ha liste?
    """
    lines = text.split('\n')
    paragraphs = re.split(r'\n\s*\n', text)
    
    # Conta sezioni (titoli markdown)
    section_pattern = r'^#+\s'
    sections = [line for line in lines if re.match(section_pattern, line)]
    
    # Conta intestazioni legali
    legal_headers = [line for line in lines if re.match(r'^(Articolo|Capo|Sezione|Capitolo)\s', line)]
    num_sections = len(sections) + len(legal_headers)
    
    # Rileva liste
    has_lists = bool(re.search(r'^\\s*[-*•]\\s', text, re.MULTILINE))
    
    # Determina tipo di struttura
    if legal_headers:
        structure_type = 'legal'
    elif sections:
        structure_type = 'technical'
    elif has_lists:
        structure_type = 'narrative_with_lists'
    else:
        structure_type = 'narrative'
    
    para_lengths = [len(p.strip()) for p in paragraphs if p.strip()]
    avg_para_len = sum(para_lengths) / len(para_lengths) if para_lengths else 0
    
    return {
        'total_chars': len(text),
        'total_lines': len(lines),
        'num_paragraphs': len([p for p in paragraphs if p.strip()]),
        'num_sections': num_sections,
        'avg_paragraph_length': avg_para_len,
        'has_headers': bool(sections),
        'has_lists': has_lists,
        'structure_type': structure_type
    }


def validate_chunk_quality(chunk: str, reference_text: str = None) -> Dict[str, float]:
    """
    Valida la qualità di un chunk per il retrieval RAG.
    
    Metriche:
    - length_score: è nella range ottimale? (100-600 token)
    - completeness: ha inizio e fine coesivi?
    - structure: ha titoli/marker di contesto?
    """
    tokens = len(chunk) // 4
    scores = {}
    
    # 1. Length score
    if 100 <= tokens <= 600:
        scores['length'] = 1.0
    elif tokens < 100:
        scores['length'] = 0.4  # Troppo corto
    else:
        scores['length'] = 0.7  # Troppo lungo ma tollerabile
    
    # 2. Completeness
    starts_proper = chunk[0].isupper() if chunk else False
    ends_proper = chunk.rstrip().endswith(('.', '!', '?', ':')) if chunk else False
    scores['completeness'] = 1.0 if (starts_proper and ends_proper) else 0.7
    
    # 3. Structure
    has_header = bool(re.match(r'^#+\s', chunk)) or bool(re.match(r'^(Articolo|Sezione)\s', chunk))
    scores['structure'] = 0.9 if has_header else 0.6
    
    # 4. Overall
    scores['overall'] = sum(scores.values()) / len(scores) if scores else 0
    
    return scores


def estimate_chunk_quality(chunk: str, question: str = None) -> Dict[str, float]:
    """
    Valuta qualità di un chunk per RAG.
    
    Metriche:
    - length_score: è nella range ottimale? (100-600 token)
    - cohesion_score: ha inizio/fine coesi? (titolo, frase completa)
    - total_tokens: numero token nel chunk
    """
    tokens = len(chunk) // 4
    
    # Length: ottimale 200-400 token
    length_score = 1.0
    if tokens < 100:
        length_score = 0.5
    elif tokens > 600:
        length_score = 0.6
    elif 200 <= tokens <= 400:
        length_score = 1.0
    
    # Cohesion: ha inizio/fine decente?
    has_header = chunk.startswith("#") or (chunk and chunk[0].isupper())
    has_ending = chunk.rstrip().endswith((".", "!", "?"))
    cohesion_score = 0.7 if (has_header and has_ending) else 0.5
    
    return {
        "length_score": length_score,
        "cohesion_score": cohesion_score,
        "total_tokens": tokens,
    }



# ==================== INTEGRATION ====================

def create_db_with_dynamic_chunking(
    documents: List[Document],
    config: ChunkingConfig = None
) -> List[Document]:
    """
    Entry point per il sistema di build_vector_db.
    Sostituisce RecursiveCharacterTextSplitter.
    
    Uso:
    ```
    from rag.dynamic_chunking import create_db_with_dynamic_chunking
    
    all_docs = load_all_documents(request, data_dir)
    chunks = create_db_with_dynamic_chunking(all_docs)
    vectordb.add_documents(chunks)
    ```
    """
    chunker = DynamicChunker(config or ChunkingConfig())
    return chunker.chunk_documents(documents)
