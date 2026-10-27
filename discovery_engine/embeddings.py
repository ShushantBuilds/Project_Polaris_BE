import os
import gc
import numpy as np

os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1' 

_model = None

def get_model():
    global _model
    if _model is None:
        import torch
        from sentence_transformers import SentenceTransformer
        
        os.environ["OMP_NUM_THREADS"] = "1"
        os.environ["MKL_NUM_THREADS"] = "1"
        torch.set_num_threads(1)
        
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model

def compute_embedding(text_or_texts):
    """
    Accepts a single string or a list of strings.
    Batch processing a list is exponentially faster than sequential calls.
    """
    vector = get_model().encode(text_or_texts, convert_to_numpy=True, normalize_embeddings=True)
    result = vector.tolist()
    
    del vector
    gc.collect()
    
    return result

def cosine_similarity(vec_a, vec_b):
    return float(np.dot(np.array(vec_a), np.array(vec_b)))