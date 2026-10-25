# IMPLEMENTATION_PLAN.md - Build Order, Milestone, and Layout

This is the how-to-build document. The method (METHOD.md) and the metrics
(EVALUATION.md) are the what. Follow the staged order so the technical risk is handled
first and the low-risk writeup work is left for the end.

---

## 1. Stack (detail)

- Python, plain. No LangChain or LlamaIndex in the core pipeline.
- Embeddings: `sentence-transformers`, model `BAAI/bge-base-en-v1.5`.
- Retrieval: plain numpy (DECIDED, as built). The corpus is 136 chunks, so `faiss`
  would add a dependency and save nothing measurable.
- Similarity matrix and metrics: numpy, with scikit-learn available if convenient.
- Graphs: matplotlib (DECIDED). Standard, simple, and what every tutorial uses.
- Config: a single `config.yaml`, loaded by `src/config.py`. Every knob lives there.
- Environment: `uv`, with torch pinned to the CPU-only wheels in `pyproject.toml` so all
  three machines produce identical similarities.

> **DECIDED (BGE usage details).** Both of bge-base-en-v1.5's easy-to-miss conventions
> are applied. Both are fixed in `src/embed.py` rather than config knobs.
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
> The prefix text is the constant `BGE_QUERY_PREFIX` in `src/embed.py`, not a config
> value, because it is decided and belongs to the model.
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
rather than content: References, External links, See also, Further reading, Notes, and
Works cited. The list of stripped section names is a config value.

Be accurate about what this step achieves, because the measured version is smaller than
the original reasoning implied. The worry was that reference lists embed strangely and
would pollute the similarity matrix. On the actual fetched text, cleaning removes only
about 2 percent of each article, because the Wikipedia plaintext extract API has already
discarded citation content: References and Works cited arrive as headings with **zero**
words underneath them, and External links is roughly 50 words. So what the step really
removes is a small links section plus a few orphan heading words. Keep it, those orphan
words would otherwise sit in a chunk as body text, but do not claim in the writeup that
it cut out a large mass of citation noise. Works cited was added to the list only after
inspecting the fetched text, where it appeared as exactly that kind of orphan heading on
the Type 1 article.

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
pairs but completely uninteresting ones, and they would inflate the count of duplicate
pairs with an artifact a viva panel would enjoy finding. Fixed windows absorb headings
mid-chunk instead.

**DECIDED (section headings): keep them as body text.** A heading line such as
"== Causes ==" is kept as the plain word "Causes" inside whatever chunk it falls in, and
only the markup is stripped. The heading words are real topic signal for retrieval, and
fixed windows already stop them from becoming their own tiny chunks. Config knob
`corpus.keep_headings: true`.

The accepted cost is that windows cut sentences mid-way. That is cosmetic for the
embedding model, and only slightly ugly when printing a chunk on a slide.

### Measured output of stage 1

Numbers from the frozen corpus at the revisions in `data/raw/MANIFEST.json`. Quote these
rather than re-deriving them, and rerun the stage if any chunking knob changes.

| Article | Raw words | Cleaned words | Chunks |
| --- | --- | --- | --- |
| Diabetes | 7,057 | 6,918 | 46 |
| Type 1 diabetes | 8,970 | 8,842 | 59 |
| Type 2 diabetes | 4,626 | 4,544 | 31 |
| **Total** | **20,653** | **20,304** | **136** |

134 of the 136 chunks are exactly 150 words. The two exceptions are the kept trailing
windows, 142 words on Type 1 and 44 on Type 2.

**136 chunks is a small corpus, and that has consequences worth flagging now.** A pool of
15 at k=3 is 11 percent of the entire corpus, and a pool of 25 at k=5 is 18 percent. The
lower end of a pool that size is genuinely weak material rather than a deep reserve of
good alternatives, which makes the pool exhaustion case in METHOD.md section 5 a
realistic event at large k. The fallback is now decided (relax, METHOD.md section 5),
and at k=3 with delta = 0.856 it is expected to be rare, since only 18 of the 9,180
corpus pairs sit above delta. In the full run it never fired at all, at k = 3, 5, 10
or 15.

> **DECIDED (short-fragment handling): drop.** Trailing stubs under `min_chunk_words`
> are discarded rather than merged into the previous chunk. This was left open until it
> could be measured, and the measurement settles it: across the whole corpus the rule
> discards **18 words**, the tail of the Diabetes article, out of 20,304. The other two
> articles end with tails of 142 and 44 words, both above the 30 word floor, so both are
> kept as slightly short chunks. Merging would recover 18 words at the cost of pushing a
> chunk to 168 words and putting length variance into the similarity distribution the
> global thresholds have to serve. Not worth it. The measured number is the viva answer.

## 3. Staged build order

Status: stages 1 to 9 are done. Stage 10 (writeup and slides) is what remains. See
docs/CHECKLIST.md.

1. Corpus prep and chunking.
2. Embedding and index build (bge-base, normalized, index or numpy matrix).
3. Vanilla top-k retrieval baseline.
4. Full MMR implementation (the comparison baseline).
5. Gate logic (signal plus trip decision).
6. Repair step (dedup plus backfill).
   Alongside 5 and 6: threshold calibration (`src/calibrate.py`,
   `scripts/calibrate.py`), which derives delta. tau is computed on the fly every run.
   See METHOD.md sections 4 and 5.
7. Evaluation harness computing every metric in EVALUATION.md (`evaluation/`).
8. Full experiment run across the dataset with results collected.
9. Result analysis, tables, and the five core graphs (EVALUATION.md, Graphs).
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

## 5. Repo layout

What exists now. Everything listed is built.

```
project/
  CLAUDE.md
  README.md
  main.py                # one query through all three methods, prints results + cost
  config.yaml            # every knob lives here
  docs/
    METHOD.md
    EVALUATION.md
    IMPLEMENTATION_PLAN.md
    FORMULAS.md          # every formula with a checkable number
    CHECKLIST.md         # short status board, read this first
  src/
    config.py            # load config.yaml, resolve repo-relative paths
    corpus.py            # load + clean + chunk the corpus
    embed.py             # bge-base embedding, normalization, similarity matrix, cache
    retrieve.py          # pool retrieval, plain top-k, backfill reserve
    gate.py              # gate signal + trip decision
    repair.py            # dedup + backfill
    mmr.py               # MMR baseline
    calibrate.py         # delta (75% rule), and tau computed on the fly (formula)
  evaluation/            # kept apart from src/, which holds only the method
    metrics.py           # ILS and relevance of a final set
    experiment.py        # run all three methods over the query set, one row each
    make_graphs.py       # run it yourself: CSVs and the five graphs into results/
  scripts/
    fetch_corpus.py      # run once, writes data/raw/*.txt and MANIFEST.json
    calibrate.py         # run when corpus, chunking, or model changes; prints delta
  tests/
    conftest.py          # the METHOD.md worked example as a fixture
    test_gate.py         # gate against the worked example
    test_calibrate.py    # tau formula, random rounding, fake duplicates
    test_metrics.py      # ILS and relevance against the worked example
  data/
    raw/                 # frozen Wikipedia text, committed
    cache/               # embeddings cache, gitignored, rebuilt automatically
    queries.json         # the query set, 50 narrow + 50 broad
  results/               # written by evaluation/make_graphs.py: per_query.csv,
                         # summary.csv, cost_vs_k.csv, figures/
```

Repair and MMR do not have tests yet (see section 8).

**DECIDED (notebooks versus modules).** `src/` holds the real code. In the end no
notebooks were needed: `main.py` covers poking at single queries, and
`evaluation/make_graphs.py` produces every figure. The rule stands if one is added
later. Notebooks import
from it and never define pipeline logic. The reasons: the worked example has to run
under `pytest`, which cannot easily import from a notebook; the comparison counters are
the number the whole contribution rests on and must not drift between copy-pasted
cells; notebook diffs are unreadable JSON and merge badly for a three-person team; and
"show me the gate" is better answered by a short `gate.py` than by scrolling a
notebook. Notebooks earn their place for the parts that are genuinely exploratory:
keeping the loaded model in memory, looking at similarity distributions to choose
thresholds, and producing report figures. Commit notebooks with outputs stripped
(`nbstripout`).

## 6. Function signatures

As implemented. Every function that touches the similarity matrix returns the number of
lookups it performed alongside its result, because compute cost in EVALUATION.md is
measured, not estimated.

```python
# config.py
def load_config(path=DEFAULT_CONFIG_PATH) -> dict: ...
def resolve_path(relative: str) -> Path: ...

# corpus.py
def load_pages(raw_dir, pages: list[str], strip_sections: list[str],
               keep_headings: bool = True) -> dict[str, str]:
    """Read the frozen raw text, cut the noise sections. Returns {page_title: text}.
    Takes the page list from config rather than listing the directory, because this
    dict's order fixes chunk id assignment and chunk id is the tie-break key."""
def chunk_pages(pages, chunk_size_words, overlap_words, min_chunk_words) -> list[Chunk]:
    """Fixed-size word windows, never crossing a page boundary. Chunk carries
    id, page, text, and word count."""

# embed.py
def embed_texts(texts, model_name, batch_size=32, device="cpu") -> np.ndarray:
    """Passages. Always L2 normalized, never prefixed."""
def embed_query(query, model_name, device="cpu") -> np.ndarray:
    """Adds BGE_QUERY_PREFIX in front of the query. Always L2 normalized."""
def similarity_matrix(embeddings) -> np.ndarray:
    """S = E @ E.T, after checking every row has length 1."""
def build_or_load_embeddings(chunk_texts, model_name, cache_path, batch_size=32,
                             device="cpu", verbose=True) -> np.ndarray:
    """Cached on disk, rebuilt whenever a fingerprint of the chunk texts and model
    name stops matching."""

# retrieve.py
def rank_by_relevance(relevance) -> list[int]:
    """All chunk ids by relevance desc, ties by chunk id asc (DECIDED tie-break)."""
def retrieve_pool(query_emb, chunk_embs, pool_size) -> list[tuple[int, float]]: ...
def plain_top_k(pool, k) -> list[int]: ...
def reserve(pool, k) -> list[tuple[int, float]]:
    """The pool after the top-k, which repair backfills from."""

# gate.py
def gate_trips(signal, tau) -> bool:
    """Strictly greater than tau trips."""
def run_gate(topk_ids, sim_matrix, tau) -> GateResult:
    """signal (simple mean of the C(k,2) pair similarities), trips, comparisons,
    and every pair, for inspection."""

# repair.py
def dedup(topk_ids, sim_matrix, relevance, delta) -> tuple[list, list, int]:
    """Iterative worst pair. Returns (kept, dropped, comparisons)."""
def backfill(kept, reserve, sim_matrix, delta, k, backfill_check="pairwise_delta",
             exhaustion_fallback="relax") -> tuple[list, list, list, list, int]:
    """Returns (kept, added, rejected, relaxed, comparisons)."""
def repair(topk_ids, reserve_pool, sim_matrix, relevance, delta, k,
           backfill_check="pairwise_delta", exhaustion_fallback="relax") -> RepairResult:
    """Dedup then backfill. final_ids, dropped, added, rejected, relaxed, comparisons."""

# mmr.py
def mmr(pool, sim_matrix, k, lambda_) -> tuple[list[int], int]:
    """(selected chunk ids, comparisons)."""

# calibrate.py
def calibrate_delta(chunks, embeddings, model_name, shared_fraction, percentile, seeds,
                    device="cpu") -> tuple[float, list[float]]:
    """(delta, per-seed values). The 75 percent shared-sentence rule."""
def typical_pair_similarity(sim_matrix, k, delta) -> float:
    """b: median non-duplicate pair similarity in pseudo-query top-k sets."""
def tau_from_delta(delta, b, k) -> float:
    """(delta + (C(k,2) - 1) * b) / C(k,2)."""
def compute_tau(sim_matrix, k, delta) -> float:
    """tau for this k, on the fly: the formula fed with b. Called once per run."""

# evaluation/metrics.py
def ils(ids, sim_matrix) -> float: ...
def mean_relevance(ids, relevance: dict) -> float: ...
# trigger rate and compute cost are averaged across queries in make_graphs.py.

# evaluation/experiment.py
def load_queries(path) -> list[dict]: ...
def run_one_query(query_emb, embeddings, sim_matrix, config, k, tau) -> dict:
    """Plain, MMR and gate for one query: final ids, comparisons, ILS, relevance."""
def run_experiment(queries, query_embs, embeddings, sim_matrix, config, k) -> list[dict]:
    """One flat row per query and method, ready for CSV."""
```

## 7. Config schema

`config.yaml` is the source of truth. Decided knobs carry a one-line comment there, and
the reasoning lives in these docs. An undecided knob gets a clearly labelled interim
default and a `NEEDS DECISION` comment, as CLAUDE.md describes. Right now every knob is
decided.

Copy as of the full evaluation run:

```yaml
model:
  name: "BAAI/bge-base-en-v1.5"
  device: "cpu"                # DECIDED: CPU keeps similarities identical on every machine
  batch_size: 32               # encoding batch size, affects speed only
  cache_path: "data/cache/embeddings.npz"   # rebuilt automatically when stale

corpus:
  raw_dir: "data/raw"
  pages:                       # DECIDED
    - "Diabetes"
    - "Type 1 diabetes"
    - "Type 2 diabetes"
  strip_sections:              # DECIDED
    - "References"
    - "External links"
    - "See also"
    - "Further reading"
    - "Notes"
    - "Works cited"
  keep_headings: true          # DECIDED: heading words kept as body text
  chunk_size_words: 150        # DECIDED
  overlap_words: 0             # DECIDED
  min_chunk_words: 30          # DECIDED: shorter trailing stubs are dropped

retrieval:
  k: 3                         # matches the worked example; real runs may use larger k
  pool_multiplier: 5           # DECIDED: pool_size = k * pool_multiplier

gate:
  tau: 0.781                   # placeholder only computed on the fly from delta and k

repair:
  delta: 0.856                 # DECIDED rule, from scripts/calibrate.py (75% shared)
  backfill_check: "pairwise_delta"   # DECIDED. unimplemented alternative : set_level_tau
  exhaustion_fallback: "relax"       # DECIDED. unimplemented alternatives : ship_fewer,
                                     # mmr_pick, relevance_floor, delta_ladder

mmr:
  lambda: 0.7                  # DECIDED

calibration:                   # read only by scripts/calibrate.py
  delta_shared_fraction: 0.75  # DECIDED: a duplicate shares about 75% of its sentences
  delta_percentile: 5          # DECIDED: delta = p5 of fake-duplicate similarities
  delta_seeds: [0, 1, 2, 3, 4] # DECIDED: average over 5 seeds to steady the estimate

evaluation:                    # read by evaluation/make_graphs.py
  queries_path: "data/queries.json"
  results_dir: "results"
  cost_vs_k: [3, 5, 10, 15]    # DECIDED: the k values for graph 2
```

## 8. Testing

- The METHOD.md worked example is the primary fixture. Both MMR and the gate method
  must return {A, C, D} on it, and the metric functions must reproduce the numbers in
  EVALUATION.md (ILS 0.50 to 0.283, relevance 0.88 to 0.853).
- Add a small synthetic case that forces the gate NOT to trip, to confirm the cheap
  path ships plain top-k untouched with only C(k,2) comparisons spent.
- Add a case that forces pool exhaustion, so the relax fallback is actually exercised.

Status: `tests/test_gate.py` covers the gate on the worked example, including a set
that does not trip. `tests/test_calibrate.py` covers the tau formula, the random
rounding, and how fake duplicates are built. `tests/test_metrics.py` checks ILS and
relevance against the worked example. All 30 tests pass (`uv run pytest`). MMR and
repair (including pool exhaustion) still have no unit tests. Both run on every query in
the full run, but neither is checked against the worked example's {A, C, D}, and a
reviewer may ask why the two functions the comparison rests on are the untested ones.

## 9. How to run

```
uv sync                                         # install, CPU-only torch
uv run pytest                                   # the worked example and calibration tests
uv run python main.py "what causes type 2 diabetes"   # one query, all three methods
uv run python evaluation/make_graphs.py         # full run: CSVs and graphs into results/
uv run python scripts/calibrate.py              # only if corpus, chunking or model change
```

The first run downloads bge-base and builds the embedding cache. Later runs reuse it.
