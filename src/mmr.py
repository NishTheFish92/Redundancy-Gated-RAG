"""Maximal Marginal Relevance baseline."""

import numpy as np


def mmr(
    pool: list[tuple[int, float]],
    sim_matrix: np.ndarray,
    k: int,
    lambda_: float,
) -> tuple[list[int], int]:
    """Run MMR, return selected chunk ids and comparison count."""
    if k > len(pool):
        raise ValueError(f"cannot select {k} from pool of {len(pool)}")

    relevance = {chunk_id: score for chunk_id, score in pool}
    remaining = [chunk_id for chunk_id, _ in pool]
    picked: list[int] = []
    comparisons = 0

    while len(picked) < k:
        best_id, best_score = None, None

        for candidate in remaining:
            if picked:
                sims = []
                for chosen in picked:
                    sims.append(float(sim_matrix[candidate][chosen]))
                    comparisons += 1
                max_sim = max(sims)
            else:
                max_sim = 0.0

            score = lambda_ * relevance[candidate] - (1.0 - lambda_) * max_sim

            if best_score is None or score > best_score or (
                score == best_score and candidate < best_id
            ):
                best_id, best_score = candidate, score

        picked.append(best_id)
        remaining.remove(best_id)

    return picked, comparisons
