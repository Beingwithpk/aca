import os
import requests
from typing import List
from src.config import EMBEDDING_MODEL

HF_API_KEY = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_KEY")
API_URL = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{EMBEDDING_MODEL}"

def get_embedding(text: str) -> List[float]:
    """Generates text embeddings via Hugging Face Serverless Inference API."""
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
    
    # If the response is wrapped in a nested batch list, extract the first vector
    if isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
        return result[0]
    return result