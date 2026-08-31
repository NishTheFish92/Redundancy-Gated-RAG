# IMPLEMENTATION_PLAN.md - Build Order, Milestone, and Layout

This is the how-to-build document. The method (METHOD.md) and the metrics
(EVALUATION.md) are the what. Follow the staged order so the technical risk is handled
first and the low-risk writeup work is left for the end.

---

## 1. Stack (detail)

- Python, plain. No LangChain or LlamaIndex in the core pipeline.
- Embeddings: `sentence-transformers`, model `BAAI/bge-base-en-v1.5`.
- Retrieval: `faiss` or plain numpy cosine. For a corpus of a few thousand chunks,
  numpy is fine and easier to explain.
- Similarity matrix and metrics: numpy, with scikit-learn available if convenient.
- Config in a single YAML or Python config module. Every knob lives there.

> **NEEDS DECISION (BGE usage details).** bge-base-en-v1.5 has two easy-to-miss
> conventions that affect correctness: embeddings are meant to be L2-normalized before
> cosine similarity, and the retrieval query is meant to carry an instruction prefix
> (the "Represent this sentence for searching relevant passages:" style prefix) while
> the passages do not. Whether to apply the prefix, and confirming normalization, both
> change the numbers. Do not silently pick one. Surface it, apply a documented default,
> and keep it configurable. Chunk-to-chunk similarity must use the same normalized
> space as query-to-chunk.

## 2. Dataset

Do not reach for a full BEIR benchmark. Use a small, controlled corpus of roughly 500
to 1500 chunks, for example chunks drawn from a handful of Wikipedia articles or a
small slice of a QA dataset such as SQuAD or HotpotQA. Small enough to sanity-check
gate behavior by hand on a few queries and to rerun experiments quickly.

> **NEEDS DECISION (corpus redundancy level).** The gate only has something to do when
> the corpus produces redundant top-k results. A corpus built from distinct,
> non-overlapping articles may almost never trip the gate, which makes the method look
> like it does nothing. A denser collection with genuine near-duplicate content
> (medical FAQ sets, product manuals, overlapping news) is closer to real RAG
> conditions and will actually exercise the gate. Choose the corpus with this in mind,
> and raise it if the early trigger rate comes out near zero. This is a data choice,
> not a reason to touch the method.

## 3. Staged build order

1. Corpus prep and chunking.
2. Embedding and index build (bge-base, normalized, index or numpy matrix).
3. Vanilla top-k retrieval baseline.
4. Full MMR implementation (the comparison baseline).
5. Gate logic (signal plus trip decision).
6. Repair step (dedup plus backfill).
7. Evaluation harness computing every metric in EVALUATION.md.
8. Full experiment run across the dataset with results collected.
9. Result analysis, tables, and the tau sensitivity sweep.
10. Writeup, slides, and any demo polish.

## 4. The 70 percent milestone

**70 percent = stages 1 through 7 working end to end.** Concretely: you can push a
query through plain top-k, full MMR, and the gate method, and get back every metric in
EVALUATION.md for all three, even if only verified on a handful of queries rather than
the full dataset.

Stages 1 through 7 hold all the technical risk. Once that pipeline runs correctly, the
rest (the full-scale run, hyperparameter sweeps, tables, and writeup) is low-risk,
time-boxed work that hands off cleanly. Hitting the milestone means the worked example
from METHOD.md passes as a test and the three methods produce comparable metric output
on a small query set.

## 5. Suggested repo layout

```
project/
  CLAUDE.md
  docs/
    METHOD.md
    EVALUATION.md
    IMPLEMENTATION_PLAN.md
  config.yaml            # every knob lives here
  src/
    corpus.py            # load + chunk the corpus
    embed.py             # bge-base embedding, normalization, index build
    retrieve.py          # pool retrieval + plain top-k
    gate.py              # gate signal + trip decision
    repair.py            # dedup + backfill
    mmr.py               # MMR baseline
    metrics.py           # all evaluation metrics
    experiment.py        # run all three methods over a query set, collect results
  tests/
    test_worked_example.py   # the METHOD.md fixture
  data/                  # corpus + queries
  results/               # experiment output tables
```

## 6. Function signatures (starting point, adjust as needed)

These are a sketch to anchor the structure, not a contract. Where a signature touches
an open decision, the decision still has to be made first.

```python
# embed.py
def embed_texts(texts: list[str], normalize: bool = True) -> np.ndarray: ...
# NEEDS DECISION: query instruction prefix (see section 1)
def embed_query(query: str) -> np.ndarray: ...

# retrieve.py
def retrieve_pool(query_emb, index, pool_size: int) -> list[tuple[int, float]]:
    """Return [(chunk_id, relevance_to_query), ...] sorted by relevance desc."""
def plain_top_k(pool: list[tuple[int, float]], k: int) -> list[int]: ...

# gate.py
def gate_signal(topk_ids: list[int], sim_matrix: np.ndarray) -> float:
    """Mean pairwise chunk-to-chunk similarity within top-k.
    NEEDS DECISION: simple mean vs weighted (see METHOD.md section 4)."""
def gate_trips(signal: float, tau: float) -> bool: ...

# repair.py
def repair(topk_ids, pool, sim_matrix, relevance, delta, k) -> list[int]:
    """Dedup then backfill. Returns final k chunk ids.
    NEEDS DECISION: multi-way redundancy rule, backfill acceptance check,
    pool-exhaustion fallback (all in METHOD.md section 5)."""

# mmr.py
def mmr(pool, query_relevance, sim_matrix, k, lambda_: float) -> list[int]: ...

# metrics.py
def ils(ids, sim_matrix) -> float: ...
def relevance_preservation(ids, query_relevance) -> float: ...
def duplicate_rate(ids, sim_matrix, delta) -> float: ...
# trigger_rate and compute_cost are computed at the experiment level, across queries.

# experiment.py
def run_all_methods(queries, corpus, config) -> ResultsTable:
    """Run plain / MMR / gate over the query set, count comparisons, collect metrics."""
```

Instrument `mmr`, `gate`, and `repair` to count the similarity comparisons they
actually perform, since compute cost in EVALUATION.md is measured, not estimated.

## 7. Config schema

Every value below is a knob. Several have interim defaults that are explicitly not
final decisions, marked accordingly. Do not move any of these into inline constants.

```yaml
model:
  name: "BAAI/bge-base-en-v1.5"
  normalize: true              # NEEDS DECISION: confirm (section 1)
  query_prefix: true           # NEEDS DECISION: apply bge query instruction? (section 1)

retrieval:
  pool_size: <undecided>       # NEEDS DECISION: must be comfortably > 2k, not just > k
  k: 3                         # matches the worked example; real runs may use larger k

gate:
  tau: <undecided>             # NEEDS DECISION: fixed vs percentile vs tuned (METHOD.md)
  averaging: "mean"            # NEEDS DECISION: mean vs weighted (METHOD.md)

repair:
  delta: <undecided>           # NEEDS DECISION: fixed vs data-driven (METHOD.md)
  multiway_rule: <undecided>   # NEEDS DECISION: how triangles are resolved (METHOD.md)
  backfill_check: <undecided>  # NEEDS DECISION: pairwise-delta vs set-level-tau (METHOD.md)
  exhaustion_fallback: <undecided>  # NEEDS DECISION: relax / ship fewer / bigger pool

mmr:
  lambda: 0.7                  # baseline knob, matches worked example
```

## 8. Testing

- The METHOD.md worked example is the primary fixture. Both MMR and the gate method
  must return {A, C, D} on it, and the metric functions must reproduce the numbers in
  EVALUATION.md (ILS 0.50 to 0.283, relevance 0.88 to 0.853, duplicate rate 33 to 0
  percent).
- Add a small synthetic case that forces the gate NOT to trip, to confirm the cheap
  path ships plain top-k untouched with only C(k,2) comparisons spent.
- Add a case that forces pool exhaustion, so the chosen fallback is actually exercised
  once that decision is made.
