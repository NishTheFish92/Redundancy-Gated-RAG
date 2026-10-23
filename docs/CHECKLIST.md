# CHECKLIST - where things stand

Fast status board. Update it when a stage lands or a decision gets made. Keep it short,
the detail belongs in the other three docs.

## Build stages

- [x] 1. Corpus prep and chunking   <-- 136 chunks, see IMPLEMENTATION_PLAN.md sec 2
- [x] 2. Embedding and similarity matrix   <-- src/embed.py, cached to data/cache
- [x] 3. Plain top-k retrieval             <-- src/retrieve.py
- [x] 4. MMR baseline                      <-- src/mmr.py
- [x] 5. Gate (signal plus trip decision)  <-- src/gate.py, tests/test_gate.py
- [x] 6. Repair (dedup plus backfill)      <-- src/repair.py, no tests yet
      Stages 2 to 6 are wired together in main.py, which runs ONE query through all
      three methods. Threshold calibration: src/calibrate.py, scripts/calibrate.py,
      tests/test_calibrate.py.
- [x] 7. Evaluation harness          <-- stages 1 to 7 are the 70 percent milestone.
                                         evaluation/, queries in data/queries.json
- [ ] 8. Full experiment run
- [ ] 9. Analysis, tables, the five core graphs (EVALUATION.md)
      evaluation/make_graphs.py draws all five, not yet run into results/
- [ ] 10. Writeup and slides

## Settled

- Layout: `src/` holds the real code, notebooks only drive and explore
- Corpus: 3 Wikipedia pages (Diabetes, Type 1, Type 2), fetched once and committed
- Cleaning: strip References, External links, See also, Further reading, Notes, Works cited
- Chunking: fixed 150 word windows, 0 overlap, drop trailing stubs under 30 words
- Short fragments: drop, not merge. Measured cost is 18 words out of 20,304
- Corpus size: 136 chunks (Diabetes 46, Type 1 59, Type 2 31), 20,304 cleaned words
- Undecided knobs get a labelled interim default plus a NEEDS DECISION comment
- Embeddings: L2 normalized, cosine equals dot product, one cached similarity matrix
- BGE query prefix: applied to queries only, never to passages
- Tie-break: relevance desc, then chunk id asc, stable sort
- k = 3 and tunable, pool_size = 5k
- MMR lambda = 0.7
- Section headings: kept as body text, markup stripped
- Gate averaging: simple mean. Weighted barely differs on BGE scores, knob removed
- Multi-way redundancy: iterative worst pair (drop one chunk, recheck). Knob removed
- Backfill check: `pairwise_delta`. Unimplemented alternative: `set_level_tau`
- Pool exhaustion: `relax` (least-similar reject). Unimplemented alternatives:
  `ship_fewer`, `mmr_pick`, `relevance_floor`, `delta_ladder`. Expected rare at k=3
- Gate/repair mismatch (mean vs tau, pairs vs delta): accepted. Some redundancy can
  reinforce facts; the risk of too much is handled by how tau and delta are set
- `delta` = 0.856 by the 75% shared-sentence rule: p5 of fake duplicates that keep 75%
  of a chunk's sentences and swap the rest for another page's, mean of 5 seeds. Flags
  18 of 9,180 pairs. Known limit: 7 of 133 neighbor pairs also flagged. METHOD.md sec 5
- `tau` = 0.807 at k=3 by formula: (delta + (C(k,2)-1) * b) / C(k,2), b = 0.782.
  Computed on the fly every run from delta and k, so changing k needs no script.
  gate.tau in config is a placeholder. scripts/calibrate.py is only for delta
  (rerun when corpus, chunking, or model changes). METHOD.md sec 4
- Delta rule uses random rounding (75% exact on average). b = median of non-duplicate
  pseudo-query top-k pairs, each chunk excluded from its own top-k
- Neighbor false-flag check: removed from code and eval, it never fed delta or tau.
  The one-time measurement (7 of 133) stays in METHOD.md sec 5 as evidence
- Duplicate rate metric: dropped, it graded the gate with its own delta (circular)
- Eval graphs, core set of 5: cost per query, cost vs k (3, 5, 10, 15), signal histogram
  with tau line, tripped vs not-tripped ILS and relevance (dot plot), ILS vs relevance
  scatter.
  Every number split tripped / not tripped. Data as CSVs in results/. Plotted with
  matplotlib. Details in EVALUATION.md
- Query set: 100 = 50 narrow (one per seed-0 sampled chunk) + 50 broad (shared
  topics), written by Claude, team reviews. Results also split broad / narrow. No
  calibration split needed. Freeze rule is a strong default, bendable as a last resort
- Evaluation code lives in evaluation/, apart from the method in src/

## Still open

- Team review of data/queries.json (an action, not a decision): read all 100, fix or
  drop bad ones, before the first real run into results/

## Gotchas to remember

BGE similarities have a high floor. Unrelated English text often scores around 0.6 to
0.7, not near 0. The METHOD.md worked example numbers are synthetic and feed a
hand-written matrix, so the test is safe, but `tau` and `delta` for the real corpus
must be read off the measured distribution. A real tau of 0.35 would trip on every
query.

The corpus is small, 136 chunks. A pool of 25 at k=5 is 18 percent of everything there
is, so backfill running out of clean candidates is realistic at large k. At k=3 with
delta 0.856 it should be rare, and the decided fallback is relax.

BGE cannot fully tell "the next paragraph on the same subject" from "a 75 percent copy".
Neighbors reach 0.896, above delta. This is a measured limit, not a bug. Say it plainly
in the writeup.

Cleaning removes only about 2 percent of each article. The Wikipedia plaintext export
had already dropped the citation text, so References arrives as an empty heading. The
cleaning step is still correct, it just is not the big cut the plan originally implied.
Do not overstate it in the writeup.
