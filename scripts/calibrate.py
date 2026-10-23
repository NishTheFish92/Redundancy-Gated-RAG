"""Derive delta from the corpus and print it for config.yaml. Takes a minute or two.

Run manually whenever the corpus, the chunking, or the embedding model changes:

    uv run python scripts/calibrate.py

It does not edit config.yaml. It prints delta and the evidence behind it, and a person
copies the number in, which keeps every change to the threshold visible in git. Changing
k does NOT need this script: tau is computed on the fly from delta and k every run. The
tau printed at the end is for information only. The rules are in src/calibrate.py and
docs/METHOD.md sections 4 and 5.
"""

import sys
from pathlib import Path

import numpy as np

# Make `src` and `main` importable when this file is run directly from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import build_index  # noqa: E402
from src.calibrate import (  # noqa: E402
    calibrate_delta,
    pseudo_query_pair_similarities,
    tau_from_delta,
    typical_pair_similarity,
)
from src.config import load_config  # noqa: E402
from src.gate import gate_trips  # noqa: E402


def main() -> None:
    config = load_config()
    model_cfg, cal_cfg = config["model"], config["calibration"]
    k = config["retrieval"]["k"]

    chunks, embeddings, sim_matrix = build_index(config)
    corpus_pairs = sim_matrix[np.triu_indices(len(chunks), 1)]

    # delta
    delta, per_seed = calibrate_delta(
        chunks,
        embeddings,
        model_cfg["name"],
        cal_cfg["delta_shared_fraction"],
        cal_cfg["delta_percentile"],
        cal_cfg["delta_seeds"],
        model_cfg["device"],
    )

    print(f"delta = {delta:.3f}")
    print(f"  rule: p{cal_cfg['delta_percentile']} of fake duplicates sharing "
          f"{cal_cfg['delta_shared_fraction']:.0%} of sentences, mean over "
          f"{len(per_seed)} seeds")
    print(f"  per seed: {', '.join(f'{d:.3f}' for d in per_seed)}  "
          f"(spread {max(per_seed) - min(per_seed):.3f})")
    print(f"  corpus pairs above delta: {(corpus_pairs > delta).sum()} of "
          f"{len(corpus_pairs)}")

    # tau, which depends on delta
    b = typical_pair_similarity(sim_matrix, k, delta)
    tau = tau_from_delta(delta, b, k)
    n_pairs = k * (k - 1) // 2
    signals = pseudo_query_pair_similarities(sim_matrix, k).reshape(-1, n_pairs).mean(1)
    trip_rate = np.mean([gate_trips(s, tau) for s in signals])

    print(f"\ntau = {tau:.3f}   (k = {k}, for information: runs compute it on the fly)")
    print(f"  b (median non-duplicate pair in a pseudo-query top-{k}) = {b:.3f}")
    print(f"  tau = (delta + {n_pairs - 1} * b) / {n_pairs}")
    print(f"  trip rate on {len(signals)} pseudo-queries: {trip_rate:.1%} "
          f"(for information only, not used to pick tau)")


if __name__ == "__main__":
    main()
