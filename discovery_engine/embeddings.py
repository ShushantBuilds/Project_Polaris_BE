import os
import gc
import urllib.request
import numpy as np

MODEL_DIR = "/tmp/minilm_onnx"
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
        tokenizer.enable_truncation(max_length=256)

        # Restrict memory arena and threads to stay well under Render's 512MB limit
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 1
        sess_options.inter_op_num_threads = 1
        sess_options.enable_cpu_mem_arena = False

        _session = ort.InferenceSession(
            MODEL_PATH,
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        )
        _tokenizer = tokenizer

    return _session, _tokenizer

def compute_embedding(text_or_texts):
    """
    Computes L2-normalized 384-d embeddings using 23MB Int8 Quantized ONNX.
    Accepts a single string or a list of strings.
    """
    is_single = isinstance(text_or_texts, str)
    inputs = [text_or_texts] if is_single else list(text_or_texts)

    session, tokenizer = _get_onnx_pipeline()
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
    token_embeddings = outputs[0]  # shape: (batch_size, seq_len, 384)

    # Mean pooling weighted by attention mask
    mask_expanded = np.expand_dims(attention_mask, axis=-1).astype(np.float32)
    sum_embeddings = np.sum(token_embeddings * mask_expanded, axis=1)
    sum_mask = np.clip(np.sum(mask_expanded, axis=1), a_min=1e-9, a_max=None)
    embeddings = sum_embeddings / sum_mask

    # L2 normalization
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    embeddings = embeddings / norms

    result = embeddings[0].tolist() if is_single else embeddings.tolist()

    del outputs, token_embeddings, embeddings
    gc.collect()

    return result

def cosine_similarity(vec_a, vec_b):
    a = np.array(vec_a, dtype=np.float32).flatten()
    b = np.array(vec_b, dtype=np.float32).flatten()
    return float(np.dot(a, b))