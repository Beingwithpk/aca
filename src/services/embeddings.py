import os
import time
import requests
from typing import List
from src.config import EMBEDDING_MODEL

# Hugging Face Router Serverless Inference endpoint
API_URL = f"https://router.huggingface.co/hf-inference/models/{EMBEDDING_MODEL}"

def _get_hf_token() -> str:
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_KEY") or ""
    return token.strip().strip("'").strip('"')


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
    hf_token = _get_hf_token()
    if not hf_token:
        raise RuntimeError("HF_TOKEN environment variable is missing or empty.")

    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json"
    }

    last_error = None
    for attempt in range(max_retries):
        try:
            response = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=45
            )

            # Cold start handling
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
        # Normalize nested lists if returned
        if len(result) > 0 and isinstance(result[0], list) and len(result[0]) > 0 and isinstance(result[0][0], list):
            return [item[0] for item in result]
        return result
    raise ValueError(f"Unexpected batch response format: {result}")