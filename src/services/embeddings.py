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