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
pairs but completely uninteresting ones, and they would inflate the duplicate-rate
metric with an artifact a viva panel would enjoy finding. Fixed windows absorb headings
mid-chunk instead.

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
realistic event rather than a rare corner. Keep that in mind when that fallback gets
decided.

> **DECIDED (short-fragment handling): drop.** Trailing stubs under `min_chunk_words`
> are discarded rather than merged into the previous chunk. This was left open until it
> could be measured, and the measurement settles it: across the whole corpus the rule
> discards **18 words**, the tail of the Diabetes article, out of 20,304. The other two
> articles end with tails of 142 and 44 words, both above the 30 word floor, so both are
> kept as slightly short chunks. Merging would recover 18 words at the cost of pushing a
> chunk to 168 words and putting length variance into the similarity distribution the
> global thresholds have to serve. Not worth it. The measured number is the viva answer.

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
# config.py
def load_config(path) -> dict: ...
def require(config: dict, dotted_key: str):
    """Fetch a config value, raising a named error if it is still null (undecided)."""

# corpus.py
def load_pages(raw_dir, pages: list[str], strip_sections: list[str],
               keep_headings: bool = True) -> dict[str, str]:
    """Read the frozen raw text, cut the noise sections. Returns {page_title: text}.
    Takes the page list from config rather than listing the directory, because this
    dict's order fixes chunk id assignment and chunk id is the tie-break key."""
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

Undecided knobs are written as `null`, which parses to Python `None`. That is deliberate:
`src/config.py` provides `require(config, "gate.tau")`, which raises a named error on a
null rather than letting an unmade decision flow into a comparison. A placeholder string
would compare without complaint and hide the fact that nobody chose the value.

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
    - "Works cited"            # added after inspecting the fetched text
  keep_headings: true          # NEEDS DECISION: keep heading words as body text (true)
                               # or drop heading lines entirely (false)
  chunk_size_words: 150        # DECIDED: fixed-size windows
  overlap_words: 0             # DECIDED: no overlap, redundancy must be real
  min_chunk_words: 30          # DECIDED: drop the trailing stub, measured cost 18 words

retrieval:
  k: 3                         # matches the worked example; real runs may use larger k
  pool_multiplier: 5           # DECIDED: pool_size = k * pool_multiplier, so k=5 -> 25
  tie_break: "chunk_id_asc"    # DECIDED: relevance desc, then chunk id asc, stable sort

gate:
  tau: null                    # NEEDS DECISION: fixed vs percentile vs tuned (METHOD.md)
  averaging: "mean"            # NEEDS DECISION: mean vs weighted (METHOD.md)

repair:
  delta: null                  # NEEDS DECISION: fixed vs data-driven (METHOD.md)
  multiway_rule: null          # NEEDS DECISION: how triangles are resolved (METHOD.md)
  backfill_check: null         # NEEDS DECISION: pairwise-delta vs set-level-tau (METHOD.md)
  exhaustion_fallback: null    # NEEDS DECISION: relax / ship fewer / bigger pool

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
