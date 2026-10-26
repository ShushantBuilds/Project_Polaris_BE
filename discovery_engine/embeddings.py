import os
from sentence_transformers import SentenceTransformer
import numpy as np

os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1' 

_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model

def compute_embedding(text_or_texts):
    """
    Accepts a single string or a list of strings.
    Batch processing a list is exponentially faster than sequential calls.
    """
    vector = get_model().encode(text_or_texts, convert_to_numpy=True, normalize_embeddings=True)
    return vector.tolist()

def cosine_similarity(vec_a, vec_b):
    return float(np.dot(np.array(vec_a), np.array(vec_b)))