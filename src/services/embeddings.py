from typing import List
from sentence_transformers import SentenceTransformer
from src.config import EMBEDDING_MODEL

_embed_model: SentenceTransformer | None = None

def get_embedding_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embed_model

def get_embedding(text: str) -> List[float]:
    model = get_embedding_model()
    # Normalize embeddings for cosine similarity
    return model.encode(text, normalize_embeddings=True).tolist()

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Splits raw text into sliding-window word chunks with overlap."""
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += (chunk_size - overlap)
    return chunks