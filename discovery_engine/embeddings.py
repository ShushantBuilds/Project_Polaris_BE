import os
import gc
import urllib.request
import numpy as np

# Store on container disk instead of /tmp (which uses RAM tmpfs on Render)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "onnx_cache")
TOKENIZER_PATH = os.path.join(MODEL_DIR, "tokenizer.json")
MODEL_PATH = os.path.join(MODEL_DIR, "model_quantized.onnx")

TOKENIZER_URL = "https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/main/tokenizer.json"
MODEL_URL = "https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/main/onnx/model_quantized.onnx"

_session = None
_tokenizer = None

def _get_onnx_pipeline():
    global _session, _tokenizer
    if _session is None or _tokenizer is None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        os.makedirs(MODEL_DIR, exist_ok=True)

        if not os.path.exists(TOKENIZER_PATH):
            urllib.request.urlretrieve(TOKENIZER_URL, TOKENIZER_PATH)
        if not os.path.exists(MODEL_PATH):
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

        tokenizer = Tokenizer.from_file(TOKENIZER_PATH)
        tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        tokenizer.enable_truncation(max_length=128)  # Cuts tensor memory in half

        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 1
        sess_options.inter_op_num_threads = 1
        sess_options.enable_cpu_mem_arena = False
        sess_options.enable_mem_pattern = False

        _session = ort.InferenceSession(
            MODEL_PATH,
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        )
        _tokenizer = tokenizer

    return _session, _tokenizer

def _embed_chunk(inputs, session, tokenizer):
    encoded = tokenizer.encode_batch(inputs)

    input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
    attention_mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
    token_type_ids = np.array([e.type_ids for e in encoded], dtype=np.int64)

    ort_inputs = {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
    }
    input_names = {inp.name for inp in session.get_inputs()}
    if "token_type_ids" in input_names:
        ort_inputs["token_type_ids"] = token_type_ids

    outputs = session.run(None, ort_inputs)
    token_embeddings = outputs[0]

    mask_expanded = np.expand_dims(attention_mask, axis=-1).astype(np.float32)
    sum_embeddings = np.sum(token_embeddings * mask_expanded, axis=1)
    sum_mask = np.clip(np.sum(mask_expanded, axis=1), a_min=1e-9, a_max=None)
    embeddings = sum_embeddings / sum_mask

    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    embeddings = embeddings / norms

    res = embeddings.tolist()
    del outputs, token_embeddings, embeddings, encoded
    return res

def compute_embedding(text_or_texts):
    is_single = isinstance(text_or_texts, str)
    inputs = [text_or_texts] if is_single else list(text_or_texts)

    session, tokenizer = _get_onnx_pipeline()

    # Process in micro-batches of 2 to keep peak RAM near zero during JIT ingestion
    all_embeddings = []
    for i in range(0, len(inputs), 2):
        chunk = inputs[i:i + 2]
        all_embeddings.extend(_embed_chunk(chunk, session, tokenizer))

    gc.collect()
    return all_embeddings[0] if is_single else all_embeddings

def cosine_similarity(vec_a, vec_b):
    a = np.array(vec_a, dtype=np.float32).flatten()
    b = np.array(vec_b, dtype=np.float32).flatten()
    return float(np.dot(a, b))