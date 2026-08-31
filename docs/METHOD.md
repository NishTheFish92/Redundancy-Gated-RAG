# METHOD.md - The Method (FIXED)

This document specifies the method. The shape of the pipeline is settled and should
not be redesigned. Where a specific rule or value is still undecided, it is marked
with a **NEEDS DECISION** callout. Those callouts are not license to redesign the
method, they are points where the team must pick a rule before you hardcode one.

---

## 1. Core idea

Standard RAG takes the k chunks most similar to the query. Those k are frequently
near-duplicates of one another, so the LLM sees the same fact several times and gets
fewer distinct pieces of evidence than the k slots suggest.

The established fix, Maximal Marginal Relevance (MMR, Carbonell and Goldstein 1998),
re-ranks a candidate pool to balance relevance against diversity. MMR and the modern
RAG methods built on the same idea share one property: they diversify on **every**
query, including the many whose top-k was already diverse and needed nothing done.

This method adds a cheap **gate** in front of a **repair** step. The gate measures how
redundant the plain top-k already is. If it is fine, ship it untouched, zero further
work. If it is redundant, run the repair. The win is that most queries pay only the
tiny gate cost and skip diversification entirely.

## 2. What makes this different from MMR

Two things, and both matter for how the contribution is framed:

1. **Conditional, not always-on.** MMR runs its full re-ranking every time. This
   method runs the repair only when the gate trips.
2. **No lambda-weighted rescoring of the whole pool each round.** MMR recomputes a
   relevance-versus-diversity score for every remaining candidate at every round.
   This method does a cheaper repair: drop the redundant members of the current set,
   then backfill the freed slots from the larger pool, checking each replacement as it
   goes. There is no continuous lambda tradeoff score.

Be honest about the consequence of point 2 when it comes up: because the repair uses
threshold checks rather than a continuous tradeoff score, it can assemble a slightly
more redundant final set than MMR would in some cases. The pitch is not "we match MMR
quality," it is "we get MMR-comparable quality on the queries that need it, at a
fraction of the average cost." Do not oversell it in comments or generated text.

## 3. The pipeline

For a single query:

1. **Retrieve a pool** larger than needed. Fetch the top `pool_size` chunks by
   query-to-chunk similarity, where `pool_size` is comfortably larger than `k`.
2. **Take the plain top-k** from the pool (the k highest-relevance chunks). Keep the
   rest of the pool as the backfill reserve.
3. **Gate check.** Compute the gate signal over the top-k (see section 4). If the
   signal is at or below `tau`, ship the plain top-k unchanged and stop here. This is
   the common, cheap path.
4. **Repair** (only if the signal exceeds `tau`). Remove redundant members of the
   top-k and backfill the freed slots from the reserve (see section 5).
5. **Return the final k chunks** to the generation step.

Everything the method contributes lives in steps 3 and 4. Keep them isolated and
inspectable.

## 4. The gate

**Signal.** Compute the pairwise chunk-to-chunk similarities within the current top-k.
There are C(k,2) such pairs, which is small (3 pairs at k=3, 10 at k=5). The gate
signal is the mean of those pairwise similarities.

**Trip decision.** If the signal is greater than `tau`, the gate trips and repair
runs. If it is at or below `tau`, the top-k ships as is.

The gate cost is fixed at C(k,2) similarity lookups per query, whether or not it
trips. This fixed, tiny cost is the whole efficiency argument, so it must be counted
honestly in evaluation (see EVALUATION.md).

> **NEEDS DECISION (gate averaging).** The signal is currently defined as a simple
> mean of the pairwise similarities. A weighted average may be better, for example
> weighting each pair by the relevance of its members so that redundancy among the
> most-relevant chunks counts for more than redundancy among borderline ones. Simple
> mean is the interim default. Do not switch to a weighted scheme without raising it,
> and if you do implement a weighted option, keep the simple mean available behind the
> same config knob so the two can be compared.

> **NEEDS DECISION (how tau is set).** It is not decided whether `tau` is a single
> fixed constant, a value chosen per corpus (for example a percentile of observed
> intra-top-k similarities), or tuned on a small dev split. Treat `tau` as a config
> value with a documented interim default, and surface this choice rather than
> quietly settling it. Note that a badly chosen `tau` breaks the whole story: too
> high and the gate never fires, too low and it fires on nearly everything and the
> efficiency advantage disappears. EVALUATION.md asks for a small sensitivity sweep
> over `tau` for exactly this reason.

## 5. The repair

Repair runs only when the gate trips. It has two parts, dedup then backfill.

**Dedup.** Find the pairs within the top-k whose similarity exceeds the duplicate
threshold `delta`, and drop the lower-relevance member so the higher-relevance chunk
is the one kept. Each drop frees a slot.

**Backfill.** Fill the freed slots from the backfill reserve, taking candidates in
relevance order. For each candidate, check it against the currently kept set. If it is
clean, keep it. If it is too similar to something already kept, reject it and move to
the next candidate. Continue until the set is back up to k or the reserve is
exhausted.

Worked through, this is a satisficing loop: walk the relevance-ordered reserve and
take the first candidates that clear the bar, rechecking each new addition against the
set already built. That iterative rechecking is deliberate and is what keeps the
backfill from reintroducing redundancy.

The following details are genuinely open. Do not assume any of them.

> **NEEDS DECISION (delta setting).** Same question as `tau`: fixed constant versus
> data-driven. Interim default is a fixed config value. `delta` (the "these two are
> duplicates" line) and `tau` (the "the set as a whole is too redundant" line) are two
> independent knobs doing two different jobs. Keep them separate in config.

> **NEEDS DECISION (multi-way redundancy).** The plain rule "drop the lower-relevance
> member of each over-delta pair" only behaves well for isolated pairs. When three or
> more chunks are all mutually similar (for example all three of the top-3 exceed
> delta with each other), applying the rule pair by pair can try to drop several
> chunks at once and over-prune. A rule that generalizes is needed, for example:
> repeatedly find the single most-similar over-delta pair, drop its lower-relevance
> member, recheck, and repeat until no pair exceeds delta. This changes how many slots
> get freed and must be decided explicitly, not improvised in code.

> **NEEDS DECISION (backfill acceptance check).** It is not fixed what a backfill
> candidate is checked against. Two reasonable options: (a) reject the candidate if
> its similarity to any already-kept chunk exceeds `delta` (a pairwise duplicate
> check), or (b) reject it if adding it would push the whole set's mean similarity back
> above `tau` (a set-level check consistent with the gate). These can give different
> final sets. Pick one deliberately and document why.

> **NEEDS DECISION (pool exhaustion fallback).** With a small reserve it is possible to
> drop members, fail to find enough clean replacements, and end up with fewer than k
> chunks and an empty reserve. This is most likely exactly when the query was most
> redundant, so it is not a rare corner to ignore. Options include: relax `delta` and
> accept the least-similar remaining candidate, ship fewer than k, or retrieve a
> larger pool up front. Decide this, and see the pool-sizing note in
> IMPLEMENTATION_PLAN.md.

> **NEEDS DECISION (similarity space).** Confirm that chunk-to-chunk similarity is
> computed in the same embedding space as query-to-chunk similarity (it should be),
> and confirm the metric (cosine is assumed). Normalization details live in
> IMPLEMENTATION_PLAN.md but affect correctness here, so do not leave them implicit.

## 6. MMR baseline (for comparison only)

MMR is not the contribution. It is implemented as the "always-on" baseline the gate
method is measured against, so it needs to be a faithful, standard MMR.

At each round, MMR picks from the remaining pool the candidate that maximizes:

    score = lambda * relevance_to_query  -  (1 - lambda) * max_similarity_to_already_picked

starting from an empty selected set and stopping at k. `lambda` is a config knob
(the project's worked example uses lambda = 0.7). Round 1 reduces to picking the most
relevant chunk. Instrument MMR to count the similarity comparisons it performs, since
its flat per-query cost is the number the gate method is compared against.

## 7. Worked example (use this as a fixture and in slides)

Query: "What causes diabetes symptoms?" Pool of 6 chunks, k = 3.

Relevance to query: A 0.90, B 0.88, C 0.86, D 0.80, E 0.75, F 0.70.
Plain top-3 = {A, B, C}.

Chunk-to-chunk similarities: A-B 0.85, A-C 0.30, A-D 0.25, A-E 0.20, A-F 0.40,
B-C 0.35, B-D 0.20, B-E 0.25, B-F 0.30, C-D 0.30, C-E 0.28, C-F 0.33, D-E 0.40,
D-F 0.35, E-F 0.30.

A and B are the near-duplicates (0.85). Knobs: delta = 0.8, tau = 0.35, lambda = 0.7.

**MMR result.** Round 1 picks A. Round 2 picks C (B scores low because it is too
similar to A). Round 3 picks D. Final = {A, C, D}.

**Gate method result.** Mean intra-top-3 similarity = (0.85 + 0.30 + 0.35) / 3 = 0.50,
which exceeds tau = 0.35, so the gate trips. A-B exceeds delta, so drop B (lower
relevance of the pair). Backfill D, check D against {A, C}: similarities 0.25 and
0.30, both clean, so keep D. Final = {A, C, D}. Same answer as MMR, reached with less
work.

Wire this example up as a unit-test fixture. Both methods should reproduce {A, C, D}
on it, and the metric functions should reproduce the numbers in EVALUATION.md.

## 8. Known edge cases to handle (not to gloss over)

- **Full redundancy triangle at small k.** See the multi-way redundancy decision above.
- **Pool exhaustion during backfill.** See the fallback decision above.
- **Gate never fires on a too-diverse corpus.** Not a bug in the method, but it makes
  results look flat. Handled at the dataset level, see IMPLEMENTATION_PLAN.md.
- **Ties in relevance ordering.** Define a deterministic tie-break so runs are
  reproducible. Flag the choice if it could affect which chunk gets kept or dropped.
