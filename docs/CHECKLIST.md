# CHECKLIST - where things stand

Fast status board. Update it when a stage lands or a decision gets made. Keep it short,
the detail belongs in the other three docs.

## Build stages

- [ ] 1. Corpus prep and chunking
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
- Cleaning: strip References, External links, See also, Further reading, Notes
- Chunking: fixed 150 word windows, 0 overlap, drop trailing stubs under 30 words
- Embeddings: L2 normalized, cosine equals dot product, one cached similarity matrix
- BGE query prefix: applied to queries only, never to passages
- Tie-break: relevance desc, then chunk id asc, stable sort
- k = 3 and tunable, pool_size = 5k
- MMR lambda = 0.7

## Still open

- `tau`: the value, and whether it is fixed, a percentile, or tuned
- `delta`: same question
- Gate averaging: simple mean vs relevance-weighted
- Multi-way redundancy: how three mutually similar chunks get resolved
- Backfill acceptance check: pairwise delta vs set-level tau
- Pool exhaustion fallback
- Query set: how many queries, and how they are generated
- Short-fragment handling: drop (current default) vs merge into previous chunk

## Gotcha to remember

BGE similarities have a high floor. Unrelated English text often scores around 0.6 to
0.7, not near 0. The METHOD.md worked example numbers are synthetic and feed a
hand-written matrix, so the test is safe, but `tau` and `delta` for the real corpus
must be read off the measured distribution. A real tau of 0.35 would trip on every
query.
