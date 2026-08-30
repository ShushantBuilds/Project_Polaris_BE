from sentence_transformers import SentenceTransformer
import numpy as np

_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model

def compute_embedding(text):
    vector = get_model().encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return vector.tolist()

def cosine_similarity(vec_a, vec_b):
    return float(np.dot(np.array(vec_a), np.array(vec_b)))