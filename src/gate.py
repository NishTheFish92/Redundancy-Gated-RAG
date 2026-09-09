"""The redundancy gate: check if top-k is redundant before repairing."""

import itertools
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class GateResult:
    """Result of one gate check."""

    signal: float
    trips: bool
    comparisons: int
    pairs: list[tuple[int, int, float]]


def pairwise_similarities(
    ids: list[int], sim_matrix: np.ndarray
) -> tuple[list[tuple[int, int, float]], int]:
    """Return every pairwise similarity within ids and lookup count."""
    if len(ids) < 2:
        raise ValueError(f"need at least 2 chunks for pairwise similarity")

    pairs: list[tuple[int, int, float]] = []
    comparisons = 0
    for i, j in itertools.combinations(ids, 2):
        pairs.append((i, j, float(sim_matrix[i][j])))
        comparisons += 1
    return pairs, comparisons


def signal_from_pairs(
    pairs: list[tuple[int, int, float]], averaging: str = "mean"
) -> float:
    """Reduce pairs to single gate signal."""
    if averaging == "mean":
        return float(np.mean([sim for _, _, sim in pairs]))
    else:
        raise NotImplementedError(f"averaging '{averaging}' not implemented")


def gate_signal(
    topk_ids: list[int], sim_matrix: np.ndarray, averaging: str = "mean"
) -> tuple[float, int]:
    """Compute gate signal and comparison count."""
    pairs, comparisons = pairwise_similarities(topk_ids, sim_matrix)
    return signal_from_pairs(pairs, averaging), comparisons


def gate_trips(signal: float, tau: float) -> bool:
    """Check if signal strictly exceeds tau."""
    return signal > tau


def run_gate(
    topk_ids: list[int],
    sim_matrix: np.ndarray,
    tau: float,
    averaging: str = "mean",
) -> GateResult:
    """Run complete gate check and return result."""
    pairs, comparisons = pairwise_similarities(topk_ids, sim_matrix)
    signal = signal_from_pairs(pairs, averaging)
    return GateResult(
        signal=signal,
        trips=gate_trips(signal, tau),
        comparisons=comparisons,
        pairs=pairs,
    )
