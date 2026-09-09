"""Pool retrieval and plain top-k baseline."""

import numpy as np


def query_relevance(query_emb: np.ndarray, chunk_embs: np.ndarray) -> np.ndarray:
    """Compute similarity of every chunk to query, shape (n,)."""
    return chunk_embs @ query_emb


def rank_by_relevance(relevance: np.ndarray) -> list[int]:
    """Sort all chunk ids by relevance descending, then id ascending."""
    return sorted(range(len(relevance)), key=lambda i: (-float(relevance[i]), i))


def retrieve_pool(
    query_emb: np.ndarray, chunk_embs: np.ndarray, pool_size: int
) -> list[tuple[int, float]]:
    """Return top pool_size chunks as (chunk_id, relevance) pairs."""
    relevance = query_relevance(query_emb, chunk_embs)
    ordered = rank_by_relevance(relevance)[:pool_size]
    return [(i, float(relevance[i])) for i in ordered]


def plain_top_k(pool: list[tuple[int, float]], k: int) -> list[int]:
    """Return k most relevant chunks without diversification."""
    return [chunk_id for chunk_id, _ in pool[:k]]


def reserve(pool: list[tuple[int, float]], k: int) -> list[tuple[int, float]]:
    """Return pool below top-k for backfill reserve."""
    return pool[k:]
