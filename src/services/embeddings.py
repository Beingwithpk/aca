import os
import requests
from typing import List
from src.config import EMBEDDING_MODEL

HF_API_KEY = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_KEY")
API_URL = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{EMBEDDING_MODEL}"

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
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
    """Generates a single vector embedding via HF Inference API."""
    clean_text = text.replace("\n", " ").strip()
    if not clean_text:
        return [0.0] * 384

    headers = {"Authorization": f"Bearer {HF_API_KEY}"} if HF_API_KEY else {}
    
    response = requests.post(
        API_URL,
        headers=headers,
        json={"inputs": clean_text, "options": {"wait_for_model": True}},
        timeout=30
    )

    if response.status_code != 200:
        raise RuntimeError(f"Embedding API error ({response.status_code}): {response.text}")

    result = response.json()
    if isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
        return result[0]
    return result


def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generates embeddings for a batch of strings."""
    if not texts:
        return []
    
    clean_texts = [t.replace("\n", " ").strip() or " " for t in texts]
    headers = {"Authorization": f"Bearer {HF_API_KEY}"} if HF_API_KEY else {}

    response = requests.post(
        API_URL,
        headers=headers,
        json={"inputs": clean_texts, "options": {"wait_for_model": True}},
        timeout=60
    )

    if response.status_code != 200:
        raise RuntimeError(f"Batch embedding API error ({response.status_code}): {response.text}")

    return response.json()