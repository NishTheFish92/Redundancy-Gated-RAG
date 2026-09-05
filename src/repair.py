"""The repair step: dedup, then backfill.

Runs only when the gate trips, which on this corpus is roughly 31 percent of queries.
Two parts, in order (METHOD.md section 5):

  Dedup.    Find pairs in the top-k above `delta` and drop the lower-relevance member of
            each, freeing slots.
  Backfill. Walk the reserve in relevance order and take the first candidates that are
            not too similar to what is already kept, until the set is back to k.

Three of the rules here are still open decisions. Each is wired to a config knob with a
labelled interim default, and each raises rather than silently guessing if it is set to a
value that has not been implemented. See config.yaml for the tradeoffs.
"""

import itertools
from dataclasses import dataclass, field

import numpy as np


@dataclass
class RepairResult:
    """Everything one repair did, so it can be inspected rather than trusted."""

    final_ids: list[int]
    dropped: list[int] = field(default_factory=list)
    added: list[int] = field(default_factory=list)
    rejected: list[int] = field(default_factory=list)
    relaxed: list[int] = field(default_factory=list)   # accepted only by the fallback
    comparisons: int = 0


def _worst_over_delta_pair(
    ids: list[int], sim_matrix: np.ndarray, delta: float
) -> tuple[tuple[int, int] | None, float, int]:
    """The most similar pair above delta, or None. Also returns the lookups it cost."""
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
    """Drop redundant members of the top-k. Returns (kept, dropped, comparisons).

    With `iterative_worst_pair`, exactly one chunk is dropped per round: take the single
    most similar over-delta pair, drop its lower-relevance member, then recheck the whole
    set. This matters when three or more chunks are mutually similar. Dropping every
    over-delta pair in one pass would remove several chunks at once and over-prune,
    because dropping one member often resolves several pairs at the same time.
    """
    if multiway_rule != "iterative_worst_pair":
        raise NotImplementedError(
            f"multiway_rule '{multiway_rule}' is not implemented. Only "
            f"'iterative_worst_pair' exists. See METHOD.md section 5, this is an open "
            f"decision."
        )

    kept = list(topk_ids)
    dropped: list[int] = []
    comparisons = 0

    while len(kept) >= 2:
        pair, _, spent = _worst_over_delta_pair(kept, sim_matrix, delta)
        comparisons += spent
        if pair is None:
            break
        # Drop the lower-relevance member so the better chunk survives. Ties go by chunk
        # id ascending, matching the project-wide rule, so the higher id is dropped.
        i, j = pair
        loser = i if (relevance[i], -i) < (relevance[j], -j) else j
        kept.remove(loser)
        dropped.append(loser)

    return kept, dropped, comparisons


def _max_sim_to_set(
    candidate: int, kept: list[int], sim_matrix: np.ndarray
) -> tuple[float, int]:
    """Highest similarity between a candidate and anything already kept, plus lookups."""
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
    """Refill the freed slots from the reserve.

    Returns (kept, added, rejected, relaxed, comparisons).

    The reserve is already in relevance order, so this is a satisficing walk: take the
    first candidate that clears the bar, then recheck every later candidate against the
    grown set. That rechecking is what stops backfill from quietly reintroducing the
    redundancy dedup just removed.
    """
    if backfill_check != "pairwise_delta":
        raise NotImplementedError(
            f"backfill_check '{backfill_check}' is not implemented. Only "
            f"'pairwise_delta' exists. The set-level alternative is an open decision, "
            f"see METHOD.md section 5."
        )

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

    # Pool exhaustion: the reserve ran out and the set is still short of k. On this corpus
    # (136 chunks, pool of 15) this is a realistic case, not a rare corner.
    if len(kept) < k:
        if exhaustion_fallback != "relax":
            raise NotImplementedError(
                f"exhaustion_fallback '{exhaustion_fallback}' is not implemented. Only "
                f"'relax' exists. See METHOD.md section 5, this is an open decision."
            )
        # Relax: take back the least-similar rejected candidates until the set is full,
        # so all three methods return exactly k chunks and their metrics stay comparable.
        # Similarities are recomputed here because the kept set changed since rejection.
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
    """Dedup then backfill. Returns the final k chunk ids and everything that happened."""
    kept, dropped, dedup_cost = dedup(
        topk_ids, sim_matrix, relevance, delta, multiway_rule
    )
    kept, added, rejected, relaxed, backfill_cost = backfill(
        kept, reserve_pool, sim_matrix, delta, k, backfill_check, exhaustion_fallback
    )

    # Return in the project's standard order: relevance descending, then chunk id.
    kept.sort(key=lambda i: (-relevance[i], i))

    return RepairResult(
        final_ids=kept,
        dropped=dropped,
        added=added,
        rejected=rejected,
        relaxed=relaxed,
        comparisons=dedup_cost + backfill_cost,
    )
