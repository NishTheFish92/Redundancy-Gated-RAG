"""Pool retrieval and the plain top-k baseline.

This is step 1 and 2 of the METHOD.md pipeline: score every chunk against the query, keep
a pool larger than k, and take the top k of it as the no-diversification baseline. The
rest of the pool is the reserve that repair backfills from.

On counting. Query-to-chunk similarities are deliberately NOT counted as "similarity
comparisons" for the compute cost metric. All three methods (plain, MMR, gate) pay the
identical retrieval cost on every query, so it cancels out of the comparison. What
EVALUATION.md is measuring is the extra chunk-to-chunk work that diversification costs,
which is where the three methods actually differ.
"""

import numpy as np


def query_relevance(query_emb: np.ndarray, chunk_embs: np.ndarray) -> np.ndarray:
    """Similarity of every chunk to the query. Shape (n,).

    Both sides are L2 normalized, so this dot product is cosine similarity, the same
    quantity the chunk-to-chunk matrix holds. That shared space is what makes it valid to
    compare a query-to-chunk score against a chunk-to-chunk one.
    """
    return chunk_embs @ query_emb


def rank_by_relevance(relevance: np.ndarray) -> list[int]:
    """All chunk ids, most relevant first.

    DECIDED tie-break (METHOD.md section 8): relevance descending, then chunk id
    ascending. Implemented as a sort key of (-relevance, chunk_id) so it holds everywhere
    an ordering is taken and runs stay reproducible.
    """
    return sorted(range(len(relevance)), key=lambda i: (-float(relevance[i]), i))


def retrieve_pool(
    query_emb: np.ndarray, chunk_embs: np.ndarray, pool_size: int
) -> list[tuple[int, float]]:
    """The top `pool_size` chunks as [(chunk_id, relevance), ...], most relevant first.

    The pool is deliberately larger than k. Its first k members are the plain top-k, and
    the remainder is the reserve repair draws replacements from.
    """
    relevance = query_relevance(query_emb, chunk_embs)
    ordered = rank_by_relevance(relevance)[:pool_size]
    return [(i, float(relevance[i])) for i in ordered]


def plain_top_k(pool: list[tuple[int, float]], k: int) -> list[int]:
    """The plain top-k baseline: the k most relevant chunks, no diversification at all.

    This is what standard RAG returns and what the whole project is arguing can be
    improved. It costs zero chunk-to-chunk comparisons, which is the number the other two
    methods are measured against.
    """
    return [chunk_id for chunk_id, _ in pool[:k]]


def reserve(pool: list[tuple[int, float]], k: int) -> list[tuple[int, float]]:
    """The backfill reserve: everything in the pool below the top-k, in relevance order."""
    return pool[k:]
