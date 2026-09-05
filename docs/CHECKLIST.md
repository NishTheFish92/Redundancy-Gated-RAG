# CHECKLIST - where things stand

Fast status board. Update it when a stage lands or a decision gets made. Keep it short,
the detail belongs in the other three docs.

## Build stages

- [x] 1. Corpus prep and chunking   <-- 136 chunks, see IMPLEMENTATION_PLAN.md sec 2
- [ ] 2. Embedding and similarity matrix
- [ ] 3. Plain top-k retrieval
- [ ] 4. MMR baseline
- [ ] 5. Gate (signal plus trip decision)
- [ ] 6. Repair (dedup plus backfill)
- [ ] 7. Evaluation harness          <-- stages 1 to 7 are the 70 percent milestone
- [ ] 8. Full experiment run
- [ ] 9. Analysis, tables, tau sweep
- [ ] 10. Writeup and slides

## Settled

- Layout: `src/` holds the real code, notebooks only drive and explore
- Corpus: 3 Wikipedia pages (Diabetes, Type 1, Type 2), fetched once and committed
- Cleaning: strip References, External links, See also, Further reading, Notes, Works cited
- Chunking: fixed 150 word windows, 0 overlap, drop trailing stubs under 30 words
- Short fragments: drop, not merge. Measured cost is 18 words out of 20,304
- Corpus size: 136 chunks (Diabetes 46, Type 1 59, Type 2 31), 20,304 cleaned words
- Undecided knobs are `null` in config.yaml, and `config.require()` errors on them
- Embeddings: L2 normalized, cosine equals dot product, one cached similarity matrix
- BGE query prefix: applied to queries only, never to passages
- Tie-break: relevance desc, then chunk id asc, stable sort
- k = 3 and tunable, pool_size = 5k
- MMR lambda = 0.7
- `delta` = 0.834 INTERIM, p99.5 of corpus pairs, checked by reading pairs at the boundary
- `tau` = 0.80 INTERIM, p70 of measured signals, matches the 30.1% of top-3 sets that
  really do contain a pair above delta. TIED TO k=3, re-derive if k changes.

## Still open

- `tau` and `delta` for the FINAL version: how they are chosen dynamically per dataset.
  Both are pinned to fixed interim values for now (see Settled).
- Gate averaging: simple mean vs relevance-weighted
- Multi-way redundancy: how three mutually similar chunks get resolved
- Backfill acceptance check: pairwise delta vs set-level tau
- Pool exhaustion fallback
- Query set: how many queries, and how they are generated
- Section headings: keep the heading words as body text (current default) vs drop them

## Gotchas to remember

BGE similarities have a high floor. Unrelated English text often scores around 0.6 to
0.7, not near 0. The METHOD.md worked example numbers are synthetic and feed a
hand-written matrix, so the test is safe, but `tau` and `delta` for the real corpus
must be read off the measured distribution. A real tau of 0.35 would trip on every
query.

The corpus is small, 136 chunks. A pool of 25 at k=5 is 18 percent of everything there
is, so backfill running out of clean candidates is a realistic case and not a rare
corner. Remember this when the pool exhaustion fallback gets decided.

Cleaning removes only about 2 percent of each article. The Wikipedia plaintext export
had already dropped the citation text, so References arrives as an empty heading. The
cleaning step is still correct, it just is not the big cut the plan originally implied.
Do not overstate it in the writeup.
