import os
import requests
import numpy as np
from decouple import config

API_URL = (
    "https://router.huggingface.co/hf-inference/models/"
    "sentence-transformers/all-MiniLM-L6-v2/pipeline/feature-extraction"
)

def get_hf_token():
    token = config("HF_API_KEY", default=os.environ.get("HF_API_KEY"))
    if not token:
        raise ValueError("HF_API_KEY environment variable is missing.")
    return token

def compute_embedding(text_or_texts):
    """
    Accepts a single string or a list of strings and returns
    L2-normalized 384-dimensional embeddings via Hugging Face API.
    """
    headers = {"Authorization": f"Bearer {get_hf_token()}"}
    payload = {
        "inputs": text_or_texts,
        "options": {"wait_for_model": True}
    }

    response = requests.post(API_URL, headers=headers, json=payload, timeout=30)

    if response.status_code != 200:
        raise RuntimeError(f"Hugging Face API Error ({response.status_code}): {response.text}")

    arr = np.array(response.json(), dtype=np.float32)

    # L2-normalize to match normalize_embeddings=True
    if arr.ndim == 1:
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
    elif arr.ndim == 2:
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        arr = arr / norms

    return arr.tolist()

def cosine_similarity(vec_a, vec_b):
    return float(np.dot(np.array(vec_a), np.array(vec_b)))