import os
import time
import requests
from typing import List
from src.config import EMBEDDING_MODEL

HF_API_KEY = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_KEY")

# Hugging Face Router Serverless Inference endpoint
API_URL = f"https://router.huggingface.co/hf-inference/models/{EMBEDDING_MODEL}"

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


def _call_hf_api(payload: dict, max_retries: int = 3) -> list:
    """Helper with automatic retries and model warm-up handling."""
    headers = {"Content-Type": "application/json"}
    if HF_API_KEY:
        headers["Authorization"] = f"Bearer {HF_API_KEY}"

    last_error = None
    for attempt in range(max_retries):
        try:
            response = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=45
            )

            # If the model is cold-starting, wait and retry
            if response.status_code == 503:
                wait_time = response.json().get("estimated_time", 10)
                time.sleep(min(wait_time, 15))
                continue

            if response.status_code == 200:
                return response.json()

            raise RuntimeError(f"HF API returned status {response.status_code}: {response.text}")

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_error = e
            time.sleep(2 * (attempt + 1))

    raise RuntimeError(f"Hugging Face Inference unreachable after {max_retries} attempts: {last_error}")


def get_embedding(text: str) -> List[float]:
    """Generates a single 384-dimensional vector embedding."""
    clean_text = text.replace("\n", " ").strip()
    if not clean_text:
        return [0.0] * 384

    result = _call_hf_api({
        "inputs": clean_text,
        "options": {"wait_for_model": True}
    })

    # The router returns either [vector] or [[vector]]
    if isinstance(result, list):
        if len(result) > 0 and isinstance(result[0], list):
            return result[0]
        return result
    raise ValueError(f"Unexpected embedding response format: {result}")


def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generates embeddings for a batch of strings."""
    if not texts:
        return []

    clean_texts = [t.replace("\n", " ").strip() or " " for t in texts]

    result = _call_hf_api({
        "inputs": clean_texts,
        "options": {"wait_for_model": True}
    })

    if isinstance(result, list):
        # When sending a list of strings, result is a list of float lists
        return result
    raise ValueError(f"Unexpected batch response format: {result}")