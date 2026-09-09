"""Embedding, similarity matrix, and embedding cache."""

import hashlib
from pathlib import Path

import numpy as np

_MODEL_CACHE: dict[tuple[str, str], object] = {}


def load_model(model_name: str, device: str = "cpu"):
    """Load sentence-transformers model, reusing within a process."""
    key = (model_name, device)
    if key not in _MODEL_CACHE:
        from sentence_transformers import SentenceTransformer

        _MODEL_CACHE[key] = SentenceTransformer(model_name, device=device)
    return _MODEL_CACHE[key]


def embed_texts(
    texts: list[str],
    model_name: str,
    normalize: bool = True,
    batch_size: int = 32,
    device: str = "cpu",
) -> np.ndarray:
    """Encode passages as shape (len(texts), 768), float32."""
    model = load_model(model_name, device)
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=normalize,
        convert_to_numpy=True,
        show_progress_bar=len(texts) > 100,
    )
    return embeddings.astype(np.float32)


def embed_query(
    query: str,
    model_name: str,
    prefix: str | None = None,
    normalize: bool = True,
    device: str = "cpu",
) -> np.ndarray:
    """Encode query as shape (768,), float32, with optional prefix."""
    text = f"{prefix}{query}" if prefix else query
    return embed_texts([text], model_name, normalize, 1, device)[0]


def check_unit_norms(embeddings: np.ndarray, tol: float = 1e-4) -> None:
    """Verify embeddings are unit length."""
    norms = np.linalg.norm(embeddings, axis=1)
    worst = float(np.max(np.abs(norms - 1.0)))
    if worst > tol:
        raise ValueError(
            f"embeddings not L2 normalized (max deviation: {worst:.6f}). "
            f"Check model.normalize in config.yaml."
        )


def similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    """Compute S = E @ E.T as chunk-to-chunk similarity matrix."""
    check_unit_norms(embeddings)
    return embeddings @ embeddings.T


def fingerprint(chunk_texts: list[str], model_name: str, normalize: bool) -> str:
    """Hash of chunk texts, model name, and normalization setting."""
    h = hashlib.sha256()
    h.update(model_name.encode("utf-8"))
    h.update(b"|normalize=" + str(bool(normalize)).encode("utf-8"))
    for text in chunk_texts:
        h.update(b"|")
        h.update(text.encode("utf-8"))
    return h.hexdigest()


def build_or_load_embeddings(
    chunk_texts: list[str],
    model_name: str,
    cache_path: str | Path,
    normalize: bool = True,
    batch_size: int = 32,
    device: str = "cpu",
    verbose: bool = True,
) -> np.ndarray:
    """Load embeddings from cache or encode if cache is stale."""
    cache_path = Path(cache_path)
    expected = fingerprint(chunk_texts, model_name, normalize)

    if cache_path.exists():
        cached = np.load(cache_path, allow_pickle=False)
        if str(cached["fingerprint"]) == expected:
            if verbose:
                print(f"embeddings: loaded {cached['embeddings'].shape} from {cache_path}")
            return cached["embeddings"]
        if verbose:
            print("embeddings: cache fingerprint mismatch, re-encoding")

    if verbose:
        print(f"embeddings: encoding {len(chunk_texts)} chunks with {model_name}")
    embeddings = embed_texts(chunk_texts, model_name, normalize, batch_size, device)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache_path, embeddings=embeddings, fingerprint=np.array(expected))
    if verbose:
        print(f"embeddings: wrote {embeddings.shape} to {cache_path}")
    return embeddings
