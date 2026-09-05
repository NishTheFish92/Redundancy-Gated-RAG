"""The redundancy gate.

This is the contribution. Everything else in the project is either setup or a baseline to
compare against. The gate answers one question as cheaply as possible:

    is the plain top-k already redundant enough to be worth repairing?

If the answer is no, the top-k ships untouched and the expensive repair never runs. That
skip, on the majority of queries, is the entire efficiency claim.

See docs/METHOD.md section 4 and docs/FORMULAS.md formulas 5 to 7.

On counting. EVALUATION.md requires compute cost to be **measured**, not derived from a
formula, so every lookup in the similarity matrix is counted as it happens. The functions
here return that count alongside their result rather than keeping a running total in
module state: a hidden counter is easy to double count and hard to defend, whereas a
returned number can be checked against C(k,2) by hand for any k.
"""

import itertools
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class GateResult:
    """What one gate check produced. Everything a reviewer might ask about is here."""

    signal: float                              # mean pairwise similarity in the top-k
    trips: bool                                # did it exceed tau
    comparisons: int                           # similarity lookups actually performed
    pairs: list[tuple[int, int, float]]        # every pair compared, for inspection


def pairwise_similarities(
    ids: list[int], sim_matrix: np.ndarray
) -> tuple[list[tuple[int, int, float]], int]:
    """Every pairwise similarity within a set of chunk ids, plus the lookup count.

    `itertools.combinations` walks each unordered pair exactly once, so the count comes
    out as C(k,2): 3 pairs at k=3, 10 at k=5. The count is incremented per lookup rather
    than computed from the formula, which is the point. If the two ever disagree, the
    implementation is wrong and the test will say so.
    """
    if len(ids) < 2:
        raise ValueError(
            f"cannot compute pairwise similarities over {len(ids)} chunk(s): a set needs "
            f"at least 2 members to have a pair. This means something upstream returned "
            f"fewer chunks than k."
        )

    pairs: list[tuple[int, int, float]] = []
    comparisons = 0
    for i, j in itertools.combinations(ids, 2):
        pairs.append((i, j, float(sim_matrix[i][j])))
        comparisons += 1
    return pairs, comparisons


def signal_from_pairs(
    pairs: list[tuple[int, int, float]], averaging: str = "mean"
) -> float:
    """Reduce already-looked-up pairs to the single gate signal.

    Kept separate from the lookups on purpose. Every similarity in this project must be
    counted exactly once, so the code that reads the matrix and the code that averages
    the result are different functions, and nothing can quietly look a pair up twice.
    """
    if averaging == "mean":
        return float(np.mean([sim for _, _, sim in pairs]))
    else:
        # NEEDS DECISION: METHOD.md section 4 leaves open whether pairs should be
        # weighted by the relevance of their members, so redundancy among the most
        # relevant chunks counts for more. Not implemented, and deliberately not
        # silently falling back to the mean, because that would hide the fact that
        # config asked for something the code does not do.
        raise NotImplementedError(
            f"gate averaging '{averaging}' is not implemented. Only 'mean' exists. "
            f"The weighted variant is an open decision, see METHOD.md section 4."
        )


def gate_signal(
    topk_ids: list[int], sim_matrix: np.ndarray, averaging: str = "mean"
) -> tuple[float, int]:
    """The gate signal: how redundant the current top-k is, as one number.

    Returns (signal, comparisons). With `averaging="mean"` this is the plain mean of the
    C(k,2) pairwise similarities, which is what METHOD.md section 4 specifies.
    """
    pairs, comparisons = pairwise_similarities(topk_ids, sim_matrix)
    return signal_from_pairs(pairs, averaging), comparisons


def gate_trips(signal: float, tau: float) -> bool:
    """Strictly greater than tau trips the gate. At or below tau ships as is.

    The comparison is strict, matching METHOD.md section 4. It matters at the boundary:
    a signal exactly equal to tau does NOT trip.
    """
    return signal > tau


def run_gate(
    topk_ids: list[int],
    sim_matrix: np.ndarray,
    tau: float,
    averaging: str = "mean",
) -> GateResult:
    """Do the whole gate check in one call and report everything about it.

    The cost is fixed at C(k,2) lookups whether or not it trips, which is what makes the
    cheap path cheap. That fixed cost is paid on every query and must be counted on every
    query, including the ones that ship the plain top-k untouched.
    """
    pairs, comparisons = pairwise_similarities(topk_ids, sim_matrix)
    signal = signal_from_pairs(pairs, averaging)
    return GateResult(
        signal=signal,
        trips=gate_trips(signal, tau),
        comparisons=comparisons,
        pairs=pairs,
    )
