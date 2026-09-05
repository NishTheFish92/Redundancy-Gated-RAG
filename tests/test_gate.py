"""Tests for the redundancy gate.

Three groups: the METHOD.md worked example reproduces exactly, the comparison counter
tells the truth, and the pieces that are still undecided refuse to guess.
"""

import numpy as np
import pytest

from src.gate import (
    gate_signal,
    gate_trips,
    pairwise_similarities,
    run_gate,
)
from tests.conftest import EXAMPLE_TAU, CountingMatrix


class TestWorkedExample:
    """METHOD.md section 7. Plain top-3 is {A, B, C}, and the gate must trip."""

    def test_signal_is_half(self, sim_matrix, plain_top3):
        # (0.85 + 0.30 + 0.35) / 3 = 0.50
        signal, _ = gate_signal(plain_top3, sim_matrix)
        assert signal == pytest.approx(0.50, abs=1e-6)

    def test_gate_trips(self, sim_matrix, plain_top3):
        assert run_gate(plain_top3, sim_matrix, EXAMPLE_TAU).trips is True

    def test_costs_three_comparisons(self, sim_matrix, plain_top3):
        assert run_gate(plain_top3, sim_matrix, EXAMPLE_TAU).comparisons == 3

    def test_reports_the_pairs_it_looked_at(self, sim_matrix, plain_top3):
        pairs = run_gate(plain_top3, sim_matrix, EXAMPLE_TAU).pairs
        assert [(i, j) for i, j, _ in pairs] == [(0, 1), (0, 2), (1, 2)]


class TestCheapPath:
    """A set that is not redundant must ship untouched, still paying exactly C(k,2)."""

    def test_diverse_set_does_not_trip(self, sim_matrix):
        # {A, C, D}: 0.30, 0.25, 0.30 -> mean 0.283, below tau 0.35
        result = run_gate([0, 2, 3], sim_matrix, EXAMPLE_TAU)
        assert result.signal == pytest.approx(0.2833, abs=1e-3)
        assert result.trips is False

    def test_cheap_path_still_pays_the_gate_cost(self, sim_matrix):
        # The fixed cost is paid whether or not the gate trips. This is the number the
        # whole efficiency argument depends on being honest about.
        assert run_gate([0, 2, 3], sim_matrix, EXAMPLE_TAU).comparisons == 3


class TestComparisonCounting:
    """The reported count must equal the reads that actually happened."""

    @pytest.mark.parametrize("k", [2, 3, 5, 10])
    def test_reported_count_matches_actual_reads(self, k):
        rng = np.random.default_rng(0)
        matrix = rng.random((k, k)).astype(np.float32)
        matrix = (matrix + matrix.T) / 2
        np.fill_diagonal(matrix, 1.0)

        counting = CountingMatrix(matrix)
        _, reported = pairwise_similarities(list(range(k)), counting)

        assert reported == counting.reads == k * (k - 1) // 2

    def test_run_gate_does_not_read_pairs_twice(self, sim_matrix, plain_top3):
        # run_gate once looked pairs up, then averaged them by looking them up again.
        # That halved the apparent cost of the gate. Guard against it coming back.
        counting = CountingMatrix(sim_matrix)
        result = run_gate(plain_top3, counting, EXAMPLE_TAU)
        assert counting.reads == 3
        assert result.comparisons == counting.reads


class TestBoundary:
    """METHOD.md section 4 says strictly greater than tau trips."""

    def test_equal_to_tau_does_not_trip(self):
        assert gate_trips(0.80, 0.80) is False

    def test_just_above_tau_trips(self):
        assert gate_trips(0.8001, 0.80) is True


class TestRefusesToGuess:
    """Undecided options must fail loudly rather than silently pick something."""

    def test_weighted_averaging_is_not_silently_the_mean(self, sim_matrix, plain_top3):
        with pytest.raises(NotImplementedError):
            gate_signal(plain_top3, sim_matrix, averaging="weighted")

    def test_a_set_with_no_pairs_errors(self, sim_matrix):
        with pytest.raises(ValueError):
            pairwise_similarities([0], sim_matrix)
