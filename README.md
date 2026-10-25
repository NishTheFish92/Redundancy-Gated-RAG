# Redundancy-Gated Retrieval: Optimized Diversification of RAG Context

Standard RAG returns the k chunks most similar to a query, and those chunks are often
near-duplicates of each other. Maximal Marginal Relevance (MMR) fixes this by
re-ranking for diversity, but it does that work on every query, including the many
whose top-k was already fine.

This project puts a cheap **gate** in front of a **repair** step. The gate looks at the
C(k,2) pair similarities inside the plain top-k (3 lookups at k = 3). If the set is not
redundant, it ships unchanged. If it is, repair drops the near-duplicates and backfills
from a larger pool. The contribution is efficiency, not beating MMR on quality.

## Result

On 100 queries over three Wikipedia articles on diabetes, at k = 3:

- The gate method spends **4.26 similarity comparisons per query on average, against
  40 for MMR**, at a 24 percent trigger rate.
- On the 24 queries where it trips, ILS (redundancy, lower is better) falls from 0.825
  to 0.795 while relevance moves only from 0.729 to 0.724. MMR reaches 0.774 at 0.722,
  so MMR diversifies more, at about five times the cost on those queries.
- On the other 76 queries the gate returns plain top-k exactly, while MMR still pays
  40 comparisons on each.
- The saving widens with k: at k = 15 the gate costs about 3 percent of MMR.

Tables, graphs and the honest weak spots are in
[docs/EVALUATION.md](docs/EVALUATION.md), section Results. Raw numbers are in
`results/`.

## Running it

Needs [uv](https://docs.astral.sh/uv/). Everything runs on CPU.

```
uv sync
uv run pytest                                          # tests on the worked example
uv run python main.py "what causes type 2 diabetes"    # one query, all three methods
uv run python evaluation/make_graphs.py                # full run into results/
```

Every knob (k, pool size, delta, lambda, model, chunking) is in `config.yaml`. tau is
computed from delta and k on every run.

## Layout

- `src/` the method: corpus, embeddings, retrieval, gate, repair, MMR, calibration
- `evaluation/` metrics, the experiment loop, and the graphs
- `scripts/` one-off tools: fetching the corpus, calibrating delta
- `data/` the frozen corpus and the 100 evaluation queries
- `results/` CSVs and figures from the full run
- `tests/` the worked example and calibration checks

## Docs

Start with [docs/CHECKLIST.md](docs/CHECKLIST.md) for status.

- [docs/METHOD.md](docs/METHOD.md) the method, every decision and its reasoning
- [docs/EVALUATION.md](docs/EVALUATION.md) metrics, graphs, and the results
- [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) stack, corpus, layout,
  function signatures, config
- [docs/FORMULAS.md](docs/FORMULAS.md) every formula with a number you can check
