"""Shared test fixtures.

The main one is the METHOD.md section 7 worked example. It feeds a hand-written
similarity matrix straight into the functions and never loads the embedding model, so it
runs in milliseconds and stays valid no matter what real BGE similarities turn out to be.
Its tau and delta are synthetic and must not be copied into config.yaml.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Chunk names A to F map to ids 0 to 5.
NAMES = "ABCDEF"

# METHOD.md section 7: relevance to the query, highest first.
RELEVANCE = np.array([0.90, 0.88, 0.86, 0.80, 0.75, 0.70], dtype=np.float32)

# METHOD.md section 7: every chunk-to-chunk similarity.
PAIR_SIMS = {
    ("A", "B"): 0.85, ("A", "C"): 0.30, ("A", "D"): 0.25, ("A", "E"): 0.20,
    ("A", "F"): 0.40, ("B", "C"): 0.35, ("B", "D"): 0.20, ("B", "E"): 0.25,
    ("B", "F"): 0.30, ("C", "D"): 0.30, ("C", "E"): 0.28, ("C", "F"): 0.33,
    ("D", "E"): 0.40, ("D", "F"): 0.35, ("E", "F"): 0.30,
}

# Synthetic knobs from the worked example. NOT the real corpus values.
EXAMPLE_TAU = 0.35
EXAMPLE_DELTA = 0.8
EXAMPLE_LAMBDA = 0.7


@pytest.fixture
def sim_matrix() -> np.ndarray:
    """The 6 by 6 similarity matrix from the worked example."""
    S = np.eye(6, dtype=np.float32)
    for (a, b), value in PAIR_SIMS.items():
        i, j = NAMES.index(a), NAMES.index(b)
        S[i][j] = S[j][i] = value
    return S


@pytest.fixture
def plain_top3() -> list[int]:
    """Plain top-3 for the worked example is {A, B, C}."""
    return [0, 1, 2]


class CountingMatrix:
    """Wraps a matrix and counts every single [i][j] read.

    This exists so tests can compare what a function *reports* it spent against what it
    *actually* spent. Compute cost is the project's headline metric, so a counter that is
    merely asserted is not good enough.
    """

    def __init__(self, matrix):
        self.matrix = matrix
        self.reads = 0

    def __getitem__(self, i):
        return _CountingRow(self.matrix[i], self)


class _CountingRow:
    def __init__(self, row, parent):
        self.row = row
        self.parent = parent

    def __getitem__(self, j):
        self.parent.reads += 1
        return self.row[j]
