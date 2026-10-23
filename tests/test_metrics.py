"""The metrics reproduce the METHOD.md worked example numbers (EVALUATION.md)."""

import pytest

from evaluation.metrics import ils, mean_relevance
from tests.conftest import RELEVANCE

A, B, C, D = 0, 1, 2, 3
RELEVANCE_BY_ID = {i: float(r) for i, r in enumerate(RELEVANCE)}


def test_ils_of_plain_top3(sim_matrix):
    # (0.85 + 0.30 + 0.35) / 3 = 0.50
    assert ils([A, B, C], sim_matrix) == pytest.approx(0.50, abs=1e-6)


def test_ils_after_repair(sim_matrix):
    # (0.30 + 0.25 + 0.30) / 3 = 0.283
    assert ils([A, C, D], sim_matrix) == pytest.approx(0.2833, abs=1e-4)


def test_relevance_of_plain_top3():
    # (0.90 + 0.88 + 0.86) / 3 = 0.88
    assert mean_relevance([A, B, C], RELEVANCE_BY_ID) == pytest.approx(0.88, abs=1e-6)


def test_relevance_after_repair():
    # (0.90 + 0.86 + 0.80) / 3 = 0.853
    assert mean_relevance([A, C, D], RELEVANCE_BY_ID) == pytest.approx(0.8533, abs=1e-4)


def test_ils_needs_a_pair(sim_matrix):
    with pytest.raises(ValueError):
        ils([A], sim_matrix)
