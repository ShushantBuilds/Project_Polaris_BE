import os
import traceback
import requests
import numpy as np
from decouple import config

API_URL = (
    "https://router.huggingface.co/hf-inference/models/"
    "sentence-transformers/all-MiniLM-L6-v2/pipeline/feature-extraction"
)

def get_hf_token():
    token = config("HF_API_KEY", default=os.environ.get("HF_API_KEY", ""))
    token = str(token).strip().strip('"').strip("'")
    if not token:
        print("CRITICAL ERROR: HF_API_KEY is missing in Render Environment!", flush=True)
        raise ValueError("HF_API_KEY environment variable is missing.")
    return token

def compute_embedding(text_or_texts):
    try:
        is_single = isinstance(text_or_texts, str)
        inputs = [text_or_texts] if is_single else list(text_or_texts)

        headers = {"Authorization": f"Bearer {get_hf_token()}"}
        payload = {
            "inputs": inputs,
            "options": {"wait_for_model": True}
        }

        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)

        if response.status_code != 200:
            print(f"HF API ERROR ({response.status_code}): {response.text}", flush=True)
            raise RuntimeError(f"HF API Error {response.status_code}: {response.text}")

        arr = np.array(response.json(), dtype=np.float32)

        # Handle 3D token embeddings if returned
        if arr.ndim == 3:
            arr = np.mean(arr, axis=1)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)

        # L2-normalize vectors
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        arr = arr / norms

        if is_single:
            return arr[0].tolist()  # Flat 1D list of 384 floats for single query
        return arr.tolist()         # 2D list of (N, 384) floats for batch

    except Exception as e:
        print(f"EMBEDDING EXCEPTION: {e}", flush=True)
        traceback.print_exc()
        raise

def cosine_similarity(vec_a, vec_b):
    a = np.array(vec_a, dtype=np.float32).flatten()
    b = np.array(vec_b, dtype=np.float32).flatten()
    return float(np.dot(a, b))