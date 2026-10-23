"""Tests for the threshold calibration rules in src/calibrate.py.

None of these load the embedding model. They check the parts of the rules that can be
checked by hand: the tau formula, the random rounding, and how fake duplicates are built.
"""

import random

import numpy as np
import pytest

from src.calibrate import (
    compute_tau,
    make_fake_duplicate,
    pseudo_query_pair_similarities,
    sentences_to_keep,
    split_sentences,
    tau_from_delta,
    typical_pair_similarity,
)


class TestTauFormula:
    def test_k3_matches_hand_calculation(self):
        # (0.856 + 2 * 0.782) / 3 = 0.80667, the number in FORMULAS.md formula 15
        assert tau_from_delta(0.856, 0.782, 3) == pytest.approx(0.80667, abs=1e-5)

    def test_k5_spreads_one_duplicate_over_ten_pairs(self):
        assert tau_from_delta(0.9, 0.7, 5) == pytest.approx((0.9 + 9 * 0.7) / 10)

    def test_compute_tau_is_the_formula_with_measured_b(self, sim_matrix):
        # compute_tau is just the formula fed with b measured on the matrix
        b = typical_pair_similarity(sim_matrix, 3, 0.8)
        assert compute_tau(sim_matrix, 3, 0.8) == pytest.approx(tau_from_delta(0.8, b, 3))

    def test_tau_sits_between_b_and_delta(self):
        tau = tau_from_delta(0.856, 0.782, 3)
        assert 0.782 < tau < 0.856


class TestRandomRounding:
    def test_whole_numbers_are_exact(self):
        # 75 percent of 8 is exactly 6, so no randomness is involved
        rng = random.Random(0)
        assert all(sentences_to_keep(8, 0.75, rng) == 6 for _ in range(100))

    def test_average_share_is_exactly_the_target(self):
        # 75 percent of 7 is 5.25, so the average kept over many draws should be 5.25
        rng = random.Random(0)
        kept = [sentences_to_keep(7, 0.75, rng) for _ in range(20000)]
        assert set(kept) == {5, 6}
        assert np.mean(kept) == pytest.approx(5.25, abs=0.02)

    def test_never_keeps_zero(self):
        assert sentences_to_keep(1, 0.1, random.Random(0)) == 1


class TestFakeDuplicate:
    ORIGINAL = [f"Original sentence {i}." for i in range(8)]
    DONOR = [f"Donor sentence {i}." for i in range(8)]

    def test_shares_the_right_number_of_sentences(self):
        fake = make_fake_duplicate(self.ORIGINAL, self.DONOR, 0.75, random.Random(0))
        parts = split_sentences(fake)
        assert sum(p in self.ORIGINAL for p in parts) == 6
        assert sum(p in self.DONOR for p in parts) == 2

    def test_kept_sentences_stay_in_original_order(self):
        fake = make_fake_duplicate(self.ORIGINAL, self.DONOR, 0.75, random.Random(3))
        kept = [p for p in split_sentences(fake) if p in self.ORIGINAL]
        assert kept == sorted(kept, key=self.ORIGINAL.index)

    def test_same_seed_gives_same_fake(self):
        a = make_fake_duplicate(self.ORIGINAL, self.DONOR, 0.75, random.Random(7))
        b = make_fake_duplicate(self.ORIGINAL, self.DONOR, 0.75, random.Random(7))
        assert a == b


class TestPseudoQueries:
    def test_a_chunk_is_never_in_its_own_top_k(self, sim_matrix):
        # Worked-example matrix, 6 chunks, k=3. Each pseudo-query gives C(3,2) = 3 pairs,
        # none of which can be a self-pair (similarity exactly 1 on the diagonal).
        pairs = pseudo_query_pair_similarities(sim_matrix, 3)
        assert len(pairs) == 6 * 3
        assert not np.any(np.isclose(pairs, 1.0))
