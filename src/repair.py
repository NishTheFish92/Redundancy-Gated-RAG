"""Repair step: dedup then backfill to improve diversity."""

import itertools
from dataclasses import dataclass, field

import numpy as np


@dataclass
class RepairResult:
    """Result of repair: final chunks and actions taken."""

    final_ids: list[int]
    dropped: list[int] = field(default_factory=list)
    added: list[int] = field(default_factory=list)
    rejected: list[int] = field(default_factory=list)
    relaxed: list[int] = field(default_factory=list)
    comparisons: int = 0


def _worst_over_delta_pair(
    ids: list[int], sim_matrix: np.ndarray, delta: float
) -> tuple[tuple[int, int] | None, float, int]:
    """Find most similar pair above delta, return pair and lookup count."""
    worst_pair, worst_sim, comparisons = None, -np.inf, 0
    for i, j in itertools.combinations(ids, 2):
        sim = float(sim_matrix[i][j])
        comparisons += 1
        if sim > delta and sim > worst_sim:
            worst_pair, worst_sim = (i, j), sim
    return worst_pair, worst_sim, comparisons


def dedup(
    topk_ids: list[int],
    sim_matrix: np.ndarray,
    relevance: dict[int, float],
    delta: float,
    multiway_rule: str = "iterative_worst_pair",
) -> tuple[list[int], list[int], int]:
    """Drop redundant members above delta, return kept/dropped/comparisons."""
    if multiway_rule != "iterative_worst_pair":
        raise NotImplementedError(f"multiway_rule '{multiway_rule}' not implemented")

    kept = list(topk_ids)
    dropped: list[int] = []
    comparisons = 0

    while len(kept) >= 2:
        pair, _, spent = _worst_over_delta_pair(kept, sim_matrix, delta)
        comparisons += spent
        if pair is None:
            break
        i, j = pair
        loser = i if (relevance[i], -i) < (relevance[j], -j) else j
        kept.remove(loser)
        dropped.append(loser)

    return kept, dropped, comparisons


def _max_sim_to_set(
    candidate: int, kept: list[int], sim_matrix: np.ndarray
) -> tuple[float, int]:
    """Get max similarity between candidate and kept set, count lookups."""
    sims = []
    for chunk_id in kept:
        sims.append(float(sim_matrix[candidate][chunk_id]))
    return (max(sims) if sims else 0.0), len(kept)


def backfill(
    kept: list[int],
    reserve: list[tuple[int, float]],
    sim_matrix: np.ndarray,
    delta: float,
    k: int,
    backfill_check: str = "pairwise_delta",
    exhaustion_fallback: str = "relax",
) -> tuple[list[int], list[int], list[int], list[int], int]:
    """Refill freed slots from reserve, return kept/added/rejected/relaxed/comparisons."""
    if backfill_check != "pairwise_delta":
        raise NotImplementedError(f"backfill_check '{backfill_check}' not implemented")

    added: list[int] = []
    rejected: list[int] = []
    relaxed: list[int] = []
    comparisons = 0

    for candidate, _ in reserve:
        if len(kept) >= k:
            break
        max_sim, spent = _max_sim_to_set(candidate, kept, sim_matrix)
        comparisons += spent
        if max_sim > delta:
            rejected.append(candidate)
        else:
            kept.append(candidate)
            added.append(candidate)

    if len(kept) < k:
        if exhaustion_fallback != "relax":
            raise NotImplementedError(f"exhaustion_fallback '{exhaustion_fallback}' not implemented")
        while len(kept) < k and rejected:
            scored = []
            for candidate in rejected:
                max_sim, spent = _max_sim_to_set(candidate, kept, sim_matrix)
                comparisons += spent
                scored.append((max_sim, candidate))
            scored.sort()
            _, best = scored[0]
            rejected.remove(best)
            kept.append(best)
            relaxed.append(best)

    return kept, added, rejected, relaxed, comparisons


def repair(
    topk_ids: list[int],
    reserve_pool: list[tuple[int, float]],
    sim_matrix: np.ndarray,
    relevance: dict[int, float],
    delta: float,
    k: int,
    multiway_rule: str = "iterative_worst_pair",
    backfill_check: str = "pairwise_delta",
    exhaustion_fallback: str = "relax",
) -> RepairResult:
    """Dedup then backfill, return repair result."""
    kept, dropped, dedup_cost = dedup(
        topk_ids, sim_matrix, relevance, delta, multiway_rule
    )
    kept, added, rejected, relaxed, backfill_cost = backfill(
        kept, reserve_pool, sim_matrix, delta, k, backfill_check, exhaustion_fallback
    )

    kept.sort(key=lambda i: (-relevance[i], i))

    return RepairResult(
        final_ids=kept,
        dropped=dropped,
        added=added,
        rejected=rejected,
        relaxed=relaxed,
        comparisons=dedup_cost + backfill_cost,
    )
