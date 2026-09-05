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

> **DECIDED (BGE usage details).** Both of bge-base-en-v1.5's easy-to-miss conventions
> are applied, and both stay configurable.
>
> **Normalization: on.** Every embedding is L2-normalized at encode time
> (`normalize_embeddings=True`), queries and passages alike. Normalizing keeps a
> vector's direction and sets its length to 1, which does three things. Cosine
> similarity becomes a plain dot product, so the entire corpus similarity matrix is
> one cached `S = E @ E.T` and every later similarity is a lookup rather than a
> calculation. Vector length, which drifts with things like verbosity, stops leaking
> into the score. And scores land in a fixed [-1, 1] range, which is the only reason a
> single global `tau` and `delta` can mean the same thing for every pair in the corpus.
>
> **Query prefix: on.** Retrieval queries carry the BGE instruction prefix,
> "Represent this sentence for searching relevant passages: ". Passages get no prefix.
> This is documented model usage and a reviewer familiar with BGE will ask about it.
> The prefix text itself is a config value so the no-prefix ablation stays one edit
> away.
>
> Note for later: BGE has a high similarity floor. Unrelated English text often scores
> around 0.6 to 0.7 rather than near 0. Expect this, measure the actual distribution
> before choosing `tau` and `delta`, and do not carry the METHOD.md worked-example
> values over to the real corpus.

## 2. Dataset

Do not reach for a full BEIR benchmark. The corpus is small and controlled so gate
behavior can be sanity-checked by hand on a few queries and experiments rerun quickly.

**DECIDED (corpus).** Three Wikipedia articles: Diabetes, Type 1 diabetes, and Type 2
diabetes. This is chosen specifically for the redundancy problem flagged below. The
three articles cover heavily overlapping ground (symptoms, causes, diagnosis,
management, complications), so genuine near-duplicate content exists **across
documents**, which is exactly the condition the gate is built for. A set of unrelated
articles would rarely trip the gate and would make the method look like it does
nothing.

**DECIDED (freezing the corpus).** Wikipedia articles change. The three articles are
fetched **once** into `data/raw/*.txt` and those files are committed. Every later run
reads from disk. This keeps results reproducible weeks later at writeup time and stops
a teammate's rerun from silently differing. The fetch script lives in `scripts/` and is
run manually, never as part of the pipeline.

**DECIDED (cleaning).** Before chunking, strip the sections that are formatting noise
rather than content: References, External links, See also, Further reading, Notes.
Reference lists in particular embed strangely and would pollute the similarity matrix.
The list of stripped section names is a config value.

### Chunking

**DECIDED: fixed-size word windows, no overlap.**

- `chunk_size_words: 150`. Windows are taken over the cleaned article text.
- `overlap_words: 0`. Overlapping chunks are near-duplicates by construction, so
  overlap would manufacture the very redundancy the method claims to find in the data.
  A reviewer can fairly attack a redundancy result built on an overlapping chunker.
  Zero overlap means every near-duplicate pair the gate finds is real.
- `min_chunk_words: 30`. The trailing window of each article can be very short. Drop
  it if it falls under the floor.
- Windows never cross article boundaries. Each of the three articles is chunked
  independently.

Why fixed-size rather than paragraph or recursive splitting: the method applies two
**global** thresholds, `tau` and `delta`, to one similarity distribution. That only
works if every chunk is a comparable object. Short chunks cover one narrow idea and
score high against anything touching it, long chunks average over several ideas and
sit in a mushy middle band, so uneven chunk lengths put a length artifact into the
similarity matrix that a single global threshold then has to serve. Fixed-size windows
give near-uniform lengths and the cleanest distribution to set thresholds against.

Fixed-size windows also sidestep a concrete trap on this corpus. All three articles
have a "Signs and symptoms" heading, a "Causes" heading, and so on. Any splitter that
respects line structure can emit those headings as their own tiny chunks, which then
match each other at very high similarity across articles. Those are real duplicate
pairs but completely uninteresting ones, and they would inflate the duplicate-rate
metric with an artifact a viva panel would enjoy finding. Fixed windows absorb headings
mid-chunk instead.

The accepted cost is that windows cut sentences mid-way. That is cosmetic for the
embedding model, and only slightly ugly when printing a chunk on a slide.

> **NEEDS DECISION (short-fragment handling).** Trailing stubs under `min_chunk_words`
> are currently dropped. Merging them into the previous chunk instead would keep every
> word at the cost of some length variance. Drop is the interim default because what it
> discards is a handful of sentence tails. Worth a one-line answer in the viva either
> way, since it explains the exact chunk count.

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
    CHECKLIST.md         # short status board, read this first
  config.yaml            # every knob lives here
  src/
    corpus.py            # load + clean + chunk the corpus
    embed.py             # bge-base embedding, normalization, similarity matrix
    retrieve.py          # pool retrieval + plain top-k
    gate.py              # gate signal + trip decision
    repair.py            # dedup + backfill
    mmr.py               # MMR baseline
    metrics.py           # all evaluation metrics
    experiment.py        # run all three methods over a query set, collect results
  scripts/
    fetch_corpus.py      # run once, writes data/raw/*.txt
  notebooks/
    01_explore_corpus.ipynb   # chunk stats, eyeball retrieval
    02_pick_thresholds.ipynb  # similarity distributions -> evidence for tau, delta
    03_results.ipynb          # tables and the tau sweep
  tests/
    test_worked_example.py   # the METHOD.md fixture
  data/
    raw/                 # frozen Wikipedia text, committed
    queries.json         # the query set
  results/               # experiment output tables
```

**DECIDED (notebooks versus modules).** `src/` holds the real code. Notebooks import
from it and never define pipeline logic. The reasons: the worked example has to run
under `pytest`, which cannot easily import from a notebook; the comparison counters are
the number the whole contribution rests on and must not drift between copy-pasted
cells; notebook diffs are unreadable JSON and merge badly for a three-person team; and
"show me the gate" is better answered by a short `gate.py` than by scrolling a
notebook. Notebooks earn their place for the parts that are genuinely exploratory:
keeping the loaded model in memory, looking at similarity distributions to choose
thresholds, and producing report figures. Commit notebooks with outputs stripped
(`nbstripout`).

## 6. Function signatures (starting point, adjust as needed)

These are a sketch to anchor the structure, not a contract. Where a signature touches
an open decision, the decision still has to be made first.

```python
# corpus.py
def load_pages(raw_dir: str, strip_sections: list[str]) -> dict[str, str]:
    """Read the frozen raw text, cut the noise sections. Returns {page_title: text}."""
def chunk_pages(pages, chunk_size_words, overlap_words, min_chunk_words) -> list[Chunk]:
    """Fixed-size word windows, never crossing a page boundary. Chunk carries
    id, text, source page, and word count."""

# embed.py
def embed_texts(texts: list[str], normalize: bool = True) -> np.ndarray: ...
def embed_query(query: str, prefix: str | None) -> np.ndarray:
    """Applies the BGE instruction prefix to the query only. Passages get none."""
def similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    """S = E @ E.T on normalized embeddings. Computed once, cached to disk."""

# retrieve.py
def retrieve_pool(query_emb, chunk_embs, pool_size: int) -> list[tuple[int, float]]:
    """Return [(chunk_id, relevance_to_query), ...] sorted by relevance desc,
    ties broken by chunk id ascending."""
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
  normalize: true              # DECIDED: L2 normalize, cosine becomes a dot product
  query_prefix: true           # DECIDED: apply the BGE retrieval instruction
  query_prefix_text: "Represent this sentence for searching relevant passages: "

corpus:
  raw_dir: "data/raw"
  pages:                       # DECIDED: overlapping content, exercises the gate
    - "Diabetes"
    - "Type 1 diabetes"
    - "Type 2 diabetes"
  strip_sections:              # DECIDED: cut before chunking
    - "References"
    - "External links"
    - "See also"
    - "Further reading"
    - "Notes"
  chunk_size_words: 150        # DECIDED: fixed-size windows
  overlap_words: 0             # DECIDED: no overlap, redundancy must be real
  min_chunk_words: 30          # DECIDED: drop the trailing stub if shorter

retrieval:
  k: 3                         # matches the worked example; real runs may use larger k
  pool_multiplier: 5           # DECIDED: pool_size = k * pool_multiplier, so k=5 -> 25
  tie_break: "chunk_id_asc"    # DECIDED: relevance desc, then chunk id asc, stable sort

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
