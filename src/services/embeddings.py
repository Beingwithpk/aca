from typing import List
from fastembed import TextEmbedding

# Cache the ONNX model in memory (~80MB RAM footprint)
_model = None


def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        # BAAI/bge-small-en-v1.5 produces normalized 384-dimensional vectors
        _model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _model


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 40) -> List[str]:
    """Splits text into overlapping word chunks."""
    words = text.split()
    if not words:
        return []

    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += (chunk_size - overlap)
        if i + overlap >= len(words) and i < len(words):
            chunks.append(" ".join(words[i:]))
            break
    return chunks


def get_embedding(text: str) -> List[float]:
    """Generates a single 384-dimensional vector embedding using local ONNX fastembed."""
    clean_text = text.replace("\n", " ").strip()
    if not clean_text:
        return [0.0] * 384

    model = get_model()
    # fastembed returns a generator of numpy arrays
    vector = list(model.embed([clean_text]))[0]
    return vector.tolist()


def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generates embeddings for a batch of strings using local ONNX fastembed."""
    if not texts:
        return []

    clean_texts = [t.replace("\n", " ").strip() or " " for t in texts]
    model = get_model()
    vectors = list(model.embed(clean_texts))
    return [v.tolist() for v in vectors]