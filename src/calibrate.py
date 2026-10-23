"""Calibration: how delta and tau are derived from the corpus.

Neither threshold is picked by hand. Both come out of a fixed rule, so rerunning the
rule on the same corpus gives the same numbers, and running it on a new corpus gives
that corpus its own thresholds. See docs/METHOD.md sections 4 and 5 and
docs/FORMULAS.md formulas 14 and 15.

  delta. "Two chunks are duplicates if they share about 75 percent of their content."
         For every chunk, build a fake duplicate that keeps 75 percent of its sentences
         and swaps the rest for sentences from an article on a different page. Score
         each fake against its original. delta is the 5th percentile of those scores,
         so a real pair is only called a duplicate once it is as similar as 95 percent
         of the fakes. Repeated over several random seeds and averaged.

  tau.   "Trip when the set is at least as redundant as one duplicate pair sitting in
         an otherwise normal top-k." That is a weighted average of delta and b, the
         typical similarity of two non-duplicate chunks in the same top-k.

This runs offline from scripts/calibrate.py. Encoding the fakes takes the embedding
model, so the results are pinned in config.yaml rather than recomputed per query.
"""

import itertools
import math
import random
import re

import numpy as np

from src.corpus import Chunk
from src.embed import embed_texts
from src.retrieve import rank_by_relevance

# Sentence boundary: ., ! or ? followed by whitespace. Simple on purpose. Chunks are
# fixed word windows, so the first and last "sentence" of a chunk can be a fragment,
# and that is fine for this purpose.
SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    """Split a chunk into sentences after collapsing all whitespace."""
    return [s for s in SENTENCE_END_RE.split(" ".join(text.split())) if s]


def sentences_to_keep(
    n_sentences: int, shared_fraction: float, rng: random.Random
) -> int:
    """How many original sentences a fake duplicate keeps, using random rounding.

    Chunks have about 8 sentences, so 75 percent is rarely a whole number. For a 7
    sentence chunk it is 5.25, so keep 5 sentences 75 percent of the time and 6
    sentences 25 percent of the time. On average every fake then shares exactly
    `shared_fraction` of its sentences. Plain rounding would not: on this corpus round
    half up averages 76.6 percent and round down averages 70.4 percent.
    """
    exact = shared_fraction * n_sentences
    keep = math.floor(exact) + (1 if rng.random() < exact - math.floor(exact) else 0)
    return max(1, keep)


def make_fake_duplicate(
    sentences: list[str],
    donor_sentences: list[str],
    shared_fraction: float,
    rng: random.Random,
) -> str:
    """A chunk that shares `shared_fraction` of its sentences with the original.

    The kept sentences are a random subset in their original order. Every removed
    sentence is replaced by one from the donor, inserted at a random position, so the
    fake has roughly the original length and genuinely different content in the
    replaced part. Replacing rather than just deleting matters: a deleted-only copy is a
    strict subset of the original, which scores far higher than two real chunks that
    share most of their content would.
    """
    n = len(sentences)
    keep_n = sentences_to_keep(n, shared_fraction, rng)
    keep_idx = sorted(rng.sample(range(n), keep_n))
    fake = [sentences[i] for i in keep_idx]
    filler = rng.sample(donor_sentences, min(n - keep_n, len(donor_sentences)))
    for sentence in filler:
        fake.insert(rng.randrange(len(fake) + 1), sentence)
    return " ".join(fake)


def fake_duplicate_similarities(
    chunks: list[Chunk],
    embeddings: np.ndarray,
    model_name: str,
    shared_fraction: float,
    seed: int,
    device: str = "cpu",
) -> np.ndarray:
    """One fake duplicate per chunk, scored against its original. Shape (n,).

    The donor for each chunk is a random chunk from a different page, so the filler is
    never a near-copy of the original by accident.
    """
    rng = random.Random(seed)
    sentences = [split_sentences(chunk.text) for chunk in chunks]
    fakes = []
    for chunk in chunks:
        donors = [c.chunk_id for c in chunks if c.page != chunk.page]
        donor_id = rng.choice(donors)
        fakes.append(
            make_fake_duplicate(
                sentences[chunk.chunk_id], sentences[donor_id], shared_fraction, rng
            )
        )
    fake_embs = embed_texts(fakes, model_name, 32, device)
    return np.sum(fake_embs * embeddings, axis=1)


def calibrate_delta(
    chunks: list[Chunk],
    embeddings: np.ndarray,
    model_name: str,
    shared_fraction: float,
    percentile: float,
    seeds: list[int],
    device: str = "cpu",
) -> tuple[float, list[float]]:
    """delta = mean over seeds of the `percentile`-th percentile of fake-duplicate
    similarities. Returns (delta, the per-seed values) so the spread can be reported."""
    per_seed = []
    for seed in seeds:
        sims = fake_duplicate_similarities(
            chunks, embeddings, model_name, shared_fraction, seed, device
        )
        per_seed.append(float(np.percentile(sims, percentile)))
    return float(np.mean(per_seed)), per_seed


def pseudo_query_pair_similarities(sim_matrix: np.ndarray, k: int) -> np.ndarray:
    """Every top-k pair similarity, using each chunk as a stand-in query.

    For chunk i, rank all OTHER chunks by similarity to i and take the top k. The chunk
    itself is excluded, otherwise it would always be its own top-1. Returns the C(k,2)
    pair similarities from every one of those top-k sets, flattened.
    """
    pair_sims = []
    for i in range(len(sim_matrix)):
        ranked = [j for j in rank_by_relevance(sim_matrix[i]) if j != i]
        for a, b in itertools.combinations(ranked[:k], 2):
            pair_sims.append(sim_matrix[a][b])
    return np.array(pair_sims)


def typical_pair_similarity(sim_matrix: np.ndarray, k: int, delta: float) -> float:
    """b: the median similarity of non-duplicate pairs inside a top-k.

    Pairs above delta are left out, since b is meant to describe a normal, duplicate-free
    pair. The median rather than the mean, so a handful of high pairs cannot drag it.
    """
    pair_sims = pseudo_query_pair_similarities(sim_matrix, k)
    return float(np.median(pair_sims[pair_sims <= delta]))


def tau_from_delta(delta: float, b: float, k: int) -> float:
    """tau = (delta + (C(k,2) - 1) * b) / C(k,2).

    The gate signal of a top-k holding exactly one pair at delta and every other pair at
    the typical level b. A set more redundant than that trips the gate.
    """
    n_pairs = k * (k - 1) // 2
    return (delta + (n_pairs - 1) * b) / n_pairs
