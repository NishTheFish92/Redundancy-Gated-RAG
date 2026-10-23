"""Evaluation metrics measured on a final set of chunks. See docs/EVALUATION.md.

These are measurements of the output, not part of any method, so they are NOT counted as
similarity comparisons. The compute cost metric counts only what a method itself spends.
"""

import itertools

import numpy as np


def ils(ids: list[int], sim_matrix: np.ndarray) -> float:
    """Intra-list similarity: mean pairwise similarity of the final set. Lower means
    less redundancy. FORMULAS.md formula 12."""
    if len(ids) < 2:
        raise ValueError(f"ILS needs at least 2 chunks, got {len(ids)}")
    return float(np.mean([sim_matrix[i][j] for i, j in itertools.combinations(ids, 2)]))


def mean_relevance(ids: list[int], relevance: dict[int, float]) -> float:
    """Relevance preservation: mean query-to-chunk similarity of the final set.
    Should barely move when redundancy is removed. FORMULAS.md formula 13."""
    return float(np.mean([relevance[i] for i in ids]))
