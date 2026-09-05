"""Maximal Marginal Relevance, the always-on baseline.

MMR is NOT the contribution. It is the established method the gate is measured against,
so it has to be a faithful, standard implementation rather than a weakened strawman. If
MMR is implemented badly the whole comparison is worthless.

Carbonell and Goldstein 1998. At each round pick the candidate maximizing

    score = lambda * relevance - (1 - lambda) * max_similarity_to_already_picked

See docs/METHOD.md section 6 and docs/FORMULAS.md formula 9.

The point of comparison is cost. MMR rescores every remaining candidate against every
already-picked chunk at every round, on every query, whether or not the query needed
diversifying. That per-query cost is the number the gate method is trying to beat.
"""

import numpy as np


def mmr(
    pool: list[tuple[int, float]],
    sim_matrix: np.ndarray,
    k: int,
    lambda_: float,
) -> tuple[list[int], int]:
    """Run MMR over the pool. Returns (selected chunk ids, comparisons performed).

    Comparisons are counted as they happen, one per lookup in the similarity matrix, so
    the number is measured rather than derived from a formula.
    """
    if k > len(pool):
        raise ValueError(f"cannot select {k} chunks from a pool of {len(pool)}")

    relevance = {chunk_id: score for chunk_id, score in pool}
    remaining = [chunk_id for chunk_id, _ in pool]
    picked: list[int] = []
    comparisons = 0

    while len(picked) < k:
        best_id, best_score = None, None

        for candidate in remaining:
            if picked:
                # One lookup per already-picked chunk. This is the cost that grows every
                # round and is paid on every query, which is exactly what the gate avoids
                # on the queries that do not need it.
                sims = []
                for chosen in picked:
                    sims.append(float(sim_matrix[candidate][chosen]))
                    comparisons += 1
                max_sim = max(sims)
            else:
                # Round 1 has an empty picked set, so it reduces to picking the most
                # relevant chunk and spends no comparisons at all.
                max_sim = 0.0

            score = lambda_ * relevance[candidate] - (1.0 - lambda_) * max_sim

            # Highest score wins, ties broken by chunk id ascending, matching the
            # project-wide rule in METHOD.md section 8.
            if best_score is None or score > best_score or (
                score == best_score and candidate < best_id
            ):
                best_id, best_score = candidate, score

        picked.append(best_id)
        remaining.remove(best_id)

    return picked, comparisons
