"""Embedding, the similarity matrix, and the embedding cache.

This turns the 136 text chunks from corpus.py into numbers. Three things happen here,
all of them decided in docs/IMPLEMENTATION_PLAN.md section 1:

  Normalization. Every embedding is L2 normalized at encode time, queries and passages
  alike. That is what makes cosine similarity a plain dot product, which is what makes
  S = E @ E.T a matrix of cosine similarities and every later similarity a lookup rather
  than a calculation. See docs/FORMULAS.md formulas 1 to 3.

  The BGE query prefix. Retrieval queries carry the instruction prefix, passages never
  do. This is documented model usage for bge-base-en-v1.5.

  Caching. Encoding is the only slow step in the project, so the embeddings are cached to
  disk. The cache stores a fingerprint of everything that determined it, and rebuilds
  itself the moment that fingerprint stops matching. Without that guard, changing a
  chunking knob and forgetting to delete the cache would give you a similarity matrix
  that does not describe your chunks, and nothing would ever error.
"""

import hashlib
from pathlib import Path

import numpy as np

# Loading the model takes a few seconds, so keep one per (name, device) for the process.
_MODEL_CACHE: dict[tuple[str, str], object] = {}


def load_model(model_name: str, device: str = "cpu"):
    """Load the sentence-transformers model, reusing it within a process.

    Imported lazily so that anything only needing corpus.py does not pay the torch
    import, which is a couple of seconds.
    """
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
    """Encode passages. No prefix is ever added here, that is queries only.

    Returns shape (len(texts), 768), float32.
    """
    model = load_model(model_name, device)
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=normalize,   # the L2 normalization step
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
    """Encode one query, applying the BGE instruction prefix if one is configured.

    Returns shape (768,), float32. The prefix goes on the query and nowhere else, which
    is the asymmetry bge-base expects. Passing prefix=None gives the no-prefix ablation.
    """
    text = f"{prefix}{query}" if prefix else query
    return embed_texts([text], model_name, normalize, 1, device)[0]


def check_unit_norms(embeddings: np.ndarray, tol: float = 1e-4) -> None:
    """Fail loudly if the embeddings are not unit length.

    Everything downstream treats a dot product as a cosine similarity, and that is only
    true for unit vectors. If normalization silently did not happen, nothing would crash,
    the numbers would just be wrong, and tau and delta would be measuring the wrong
    quantity. So it is checked rather than assumed.
    """
    norms = np.linalg.norm(embeddings, axis=1)
    worst = float(np.max(np.abs(norms - 1.0)))
    if worst > tol:
        raise ValueError(
            f"embeddings are not L2 normalized: largest deviation from length 1 is "
            f"{worst:.6f}. Cosine similarity is not a dot product here, so S would be "
            f"wrong. Check model.normalize in config.yaml."
        )


def similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    """S = E @ E.T, the chunk-to-chunk similarity of every pair.

    Shape (n, n), symmetric, diagonal 1. Built once and held in memory, so from here on
    one similarity comparison means exactly one lookup in S, which is what makes the
    compute cost in EVALUATION.md countable instead of estimated.
    """
    check_unit_norms(embeddings)
    return embeddings @ embeddings.T


def fingerprint(chunk_texts: list[str], model_name: str, normalize: bool) -> str:
    """A hash of everything that determines the embeddings.

    Hashing the chunk texts themselves rather than the config knobs that produced them
    is deliberate: it covers the raw corpus, the cleaning rules and all three chunking
    knobs at once, and it cannot drift out of date when a new knob gets added.
    """
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
    """Return the chunk embeddings, encoding them only if the cache cannot be trusted.

    The cache is rebuilt whenever the fingerprint differs, so a stale cache is not
    something anyone has to remember to clear.
    """
    cache_path = Path(cache_path)
    expected = fingerprint(chunk_texts, model_name, normalize)

    if cache_path.exists():
        cached = np.load(cache_path, allow_pickle=False)
        if str(cached["fingerprint"]) == expected:
            if verbose:
                print(f"embeddings: loaded {cached['embeddings'].shape} from {cache_path}")
            return cached["embeddings"]
        if verbose:
            print("embeddings: cache fingerprint does not match, re-encoding")

    if verbose:
        print(f"embeddings: encoding {len(chunk_texts)} chunks with {model_name}")
    embeddings = embed_texts(chunk_texts, model_name, normalize, batch_size, device)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache_path, embeddings=embeddings, fingerprint=np.array(expected))
    if verbose:
        print(f"embeddings: wrote {embeddings.shape} to {cache_path}")
    return embeddings
