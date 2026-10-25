# METHOD.md - The Method (FIXED)

This document specifies the method. The shape of the pipeline is settled and should
not be redesigned. Every rule that was once open is now marked **DECIDED** with its
reasoning, and no **NEEDS DECISION** callouts remain. The method is fully implemented
in `src/`, and its measured behaviour on the full query set is in EVALUATION.md,
Results.

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

> **DECIDED (gate averaging): simple mean.** A relevance-weighted mean was considered,
> where each pair counts more when its members are more relevant, so redundancy at the
> top of the list matters most. It was rejected for two reasons. First, BGE relevances
> inside a top-k sit very close together (for example 0.78, 0.76, 0.75), so the weights
> come out nearly equal and the weighted signal is almost the same number as the mean.
> Second, it brings its own extra decision (which weight formula) and is harder to
> explain, for almost no effect. The `averaging` knob was removed from config.

> **DECIDED (how tau is set): derived from `delta` and `k` by a formula.** The rule in
> words: **trip when the set is at least as redundant as one duplicate pair sitting in an
> otherwise normal top-k.**
>
>     tau = (delta + (C(k,2) - 1) * b) / C(k,2)
>
> `b` is the typical similarity of two chunks that share a top-k without being
> duplicates. It is measured on pseudo-queries: each of the 136 chunks stands in as a
> query, its top-k is taken from the other 135 chunks (the chunk itself is excluded, or
> it would always be its own top-1), and `b` is the median of all the pair similarities
> in those top-k sets that are at or below `delta`.
>
> **DECIDED: tau is computed on the fly.** `compute_tau` in `src/calibrate.py` runs
> once at the start of every run (main.py and the evaluation), from the current
> `delta`, `k`, and similarity matrix. It needs no model and takes milliseconds, so
> changing k never needs a recalibration step and tau can never be stale. `gate.tau` in
> config.yaml is only a placeholder and is never read. Being calibration rather than
> part of answering a query, its lookups are not counted as comparisons.
>
> Current values, k = 3: `b` = 0.782, so tau = (0.856 + 2 * 0.782) / 3 = **0.807**. At
> k = 5 the same rule gives `b` = 0.772 and tau = 0.780.
>
> Why this rule:
> - **It handles k.** More pairs dilute the mean, so a fixed tau that suits k = 3 fires
>   on almost nothing at k = 5. The formula re-derives itself for any k.
> - **It handles BGE's high floor.** `b` is measured, so tau sits just above what a
>   normal top-k looks like on this corpus, whatever that level is.
> - **It is not circular.** tau is never picked to produce a particular trigger rate,
>   so the trigger rate stays a finding rather than a restatement of the choice.
>
> For information only: on the 136 pseudo-queries at k = 3 the gate trips on 24.3
> percent, while 18.4 percent of the top-3 sets contain a pair above `delta`. The two
> do not have to match, see the gate and repair note in section 5.
>
> History. The interim value was 0.80, set at p70 of the measured signal so the trigger
> rate matched the share of top-3 sets holding a pair above the old `delta` of 0.834.
> It was replaced because it was tied to k = 3 and had to be re-derived by hand.
>
> **DECIDED (how `b` is measured).** The median rather than the mean, so a few unusual
> pairs cannot drag it. Pairs above `delta` are left out, since `b` describes a normal,
> duplicate-free pair. And each chunk is excluded from its own top-k, or it would always
> be its own top-1.
>
> **Caveat.** `b` comes from chunks standing in as queries. It could in principle be
> re-measured on real queries, but only on a calibration split, never on the queries
> the results are reported on. The query set was decided with no calibration split
> (EVALUATION.md, Query set), so `b` stays on the pseudo-queries and all 100 real
> queries are used only for evaluation.
>
> Measured on the real queries: the gate trips on 24 percent at k = 3, close to the
> 24.3 percent seen on the pseudo-queries.
>
> EVALUATION.md's sensitivity sweep over `tau` still applies.

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

The details below were open and are now settled, each with its reasoning.

> **DECIDED (how delta is set): the 75 percent shared-sentence rule.** The definition:
> **two chunks are duplicates if they share about 75 percent of their content.** Real
> redundancy in RAG is rarely a perfect copy. It is mostly the same facts restated, as
> when the Diabetes and Type 2 articles both explain insulin resistance. `delta` is set
> to catch that, not only verbatim copies. The exact rule, in `src/calibrate.py`:
>
> 1. **Split** every chunk into sentences, breaking after `.`, `!` or `?` followed by
>    whitespace.
> 2. **Build one fake duplicate per chunk.** Keep 75 percent of its sentences, chosen at
>    random, in their original order. Replace each removed sentence with a random
>    sentence from a donor chunk, picked at random from a **different** page, inserted
>    at a random position. The fake is about the same length as the original and its
>    replaced part is genuinely different content.
> 3. **Round at random.** 75 percent of a chunk is rarely a whole number of sentences.
>    For 7 sentences it is 5.25, so keep 5 sentences 75 percent of the time and 6
>    sentences 25 percent of the time. On average every fake shares exactly 75 percent.
>    A minimum of 1 sentence is always kept.
> 4. **Score** every fake against its own original (cosine similarity).
> 5. **Take the 5th percentile** of those 136 scores. A real pair is a duplicate only
>    once it is as similar as 95 percent of the fakes.
> 6. **Repeat over 5 seeds** (0 to 4) and average the five results.
>
> Result: **delta = 0.856**. Per-seed values 0.849 to 0.861, a spread of 0.012. It flags
> **18 of the 9,180** corpus pairs. Settings: `calibration` section of config.yaml.
>
> Why replace sentences rather than delete them. A copy with 25 percent deleted is a
> strict subset of its original and scores far higher (p5 near 0.92) than two real chunks
> that share most of their content, each with some text of their own. Replacing models
> the real case.
>
> **Known limitation: 7 of 133 neighbor pairs score above delta.** Consecutive chunks on
> the same page share **no** sentences (chunking has zero overlap), so by the definition
> none of them are duplicates. Yet seven are flagged, with neighbors reaching up to
> 0.896. BGE scores "the next paragraph on the same subject" about the same as "a 75
> percent copy", and no single similarity threshold can fully separate the two. This is
> a limit of single-vector similarity, which MMR shares without saying so. The cost of
> a false flag is small and measurable: the flagged chunk is replaced by the next most
> relevant clean one, and relevance preservation in EVALUATION.md shows whether that
> hurts. The well-known pair c0 and c1 (the first two chunks of the Diabetes article,
> 0.823) is not flagged.
>
> The neighbor counts in this section were measured once, while choosing the rule. The
> code no longer computes them (DECIDED: the check was removed to keep calibration
> lean, since it never fed into delta or tau). They stay here as the evidence behind
> the 75 percent choice and the known limitation.
>
> Why 75 percent and not another level. The 70 and 80 percent rows were an early
> exploration on one seed with round half to even, so they are indicative rather than
> exact. The 75 percent row is the final rule.
>
> | Shared | delta | Corpus pairs flagged | Neighbors flagged |
> | --- | --- | --- | --- |
> | 70% | 0.823 | 73 | 19 of 133 |
> | **75% (final)** | **0.856** | **18** | **7 of 133** |
> | 80% | 0.891 | 4 | 1 of 133 |
>
> 70 percent flags too many neighbors. 80 percent flags so few pairs that repair would
> almost never act. 75 percent sits between them.
>
> **DECIDED (random rounding in step 3).** It is the only option that makes the fakes
> share exactly 75 percent on average. The alternatives move delta only slightly. Round half up averages 76.6 percent shared and
> gives 0.865. Round half to even averages 73.9 percent and gives 0.857.
>
> History. The interim value was 0.834, p99.5 of the corpus pair distribution, chosen by
> reading six pairs at the boundary so that c0/c1 would not be flagged. It was replaced
> because a percentile assumes a fixed share of pairs are duplicates on any corpus, and
> because it still flagged 15 of the 133 neighbor pairs.
>
> `delta` (the "these two are duplicates" line) and `tau` (the "the set as a whole is
> too redundant" line) remain two different knobs doing two different jobs. tau is
> derived from delta, but they are not the same thing.

> **DECIDED (multi-way redundancy): iterative worst pair.** When three or more chunks
> are mutually similar, repair drops one chunk at a time: find the single most similar
> pair above `delta`, drop its lower-relevance member, recheck the remaining set, and
> repeat until no pair exceeds `delta`. The alternative, dropping the lower member of
> every over-delta pair in one pass, over-prunes. Example: A-B 0.95, B-C 0.90, A-C 0.70.
> One pass drops B and C and keeps only {A}, even though C was never similar to A. The
> iterative rule drops B, rechecks, finds A-C fine, and keeps {A, C}. This is now simply
> how dedup works, so it is not a config knob.

> **DECIDED (backfill acceptance check): pairwise against `delta`.** A candidate is
> rejected if its similarity to any already-kept chunk exceeds `delta`. Reasons: dedup
> and backfill then share one definition of "duplicate"; no pair above `delta` survives
> repair (except through the exhaustion fallback below); a true near-duplicate cannot
> sneak in by being averaged against diverse chunks; and it does not depend on `tau`,
> which is the least settled knob and is tied to k. The rejected alternative,
> `set_level_tau`, rejects a candidate only if adding it pushes the set mean above
> `tau`. It is consistent with the gate, but it can readmit a real duplicate. Example:
> kept {A, C} with A-C 0.70, candidate D with D-A 0.86 and D-C 0.60. The mean is 0.72,
> so set_level_tau accepts D even though it duplicates A. The knob stays in config with
> `set_level_tau` listed as an unimplemented alternative.

> **DECIDED (pool exhaustion fallback): relax.** If the reserve runs out before the set
> is back to k, take back the rejected candidate least similar to the kept set, and
> repeat until there are k chunks. This keeps every method returning exactly k chunks,
> so ILS, relevance and cost compare fairly across plain, MMR and gate. The accepted
> cost is that the "no pair above `delta`" guarantee breaks for that query, which is
> acceptable because a certain amount of redundancy can reinforce facts. It is also
> expected to be rare at k=3: `delta` flags only 18 of 9,180 corpus pairs, so the whole
> reserve would have to be duplicates of a kept chunk. Alternatives considered and left
> unimplemented for now, to be revisited during evaluation if relax turns out to matter:
> `ship_fewer` (return fewer than k), `mmr_pick` (pick the reject with the best MMR
> score), `relevance_floor` (least similar, but only among rejects close in relevance
> to the top chunk), and `delta_ladder` (raise `delta` a fixed number of times and take
> the most relevant reject that passes, then fall back to relax).
>
> **Measured: relax never fired.** Across all 100 evaluation queries at k = 3, 5, 10
> and 15, no query ran out of clean candidates. Relax did not turn out to matter, so the
> alternatives were not needed.

> **DECIDED (gate and repair use different tests).** The gate trips on the set mean
> against `tau`, while dedup acts on single pairs against `delta`. These do not always
> agree. A set with every pair at 0.82 trips the gate (mean above 0.807) but has no pair
> above 0.856, so repair changes nothing and the 3 gate comparisons buy nothing. A set
> with one pair at 0.90 and two at 0.65 has a mean of 0.73, does not trip, and ships
> its duplicate. This is accepted, not fixed: a certain amount of redundancy can
> reinforce context and facts rather than waste it. The real risk is too much
> redundancy getting through, for example if `tau` were set so high that the gate
> almost never trips, and that is handled when `tau` and `delta` are set.
>
> **Measured: 9 of the 24 tripped queries came out unchanged** at k = 3. Their mean was
> above tau but no pair was above delta, so each spent 6 comparisons (3 gate, 3 dedup)
> and shipped plain top-k anyway. This is the first case above, and it is in the
> results as a stated weak spot (EVALUATION.md, Results).

> **DECIDED (similarity space).** All embeddings are L2-normalized at encode time, so
> cosine similarity is a plain dot product. Queries and passages are normalized
> identically, which is what guarantees query-to-chunk and chunk-to-chunk similarity
> live in the same space. The whole corpus similarity matrix is computed once as
> `S = E @ E.T` and cached, so nothing recomputes a similarity at run time and one
> "similarity comparison" means exactly one lookup in `S`. See
> IMPLEMENTATION_PLAN.md section 1.

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

**These numbers are synthetic and that is deliberate.** The fixture feeds a
hand-written similarity matrix straight into the functions, it does not run the
embedding model. So the test stays valid no matter what real BGE similarities turn out
to be. Do not read the example's `delta = 0.8` and `tau = 0.35` as starting values for
the real corpus. BGE has a high similarity floor: unrelated English text commonly
scores around 0.6 to 0.7 rather than near 0, so a real `tau` of 0.35 would trip on
every query. Real thresholds must be read off the measured distribution, which is what
the calibration in sections 4 and 5 does.

## 8. Known edge cases to handle (not to gloss over)

- **Full redundancy triangle at small k.** DECIDED, see the multi-way redundancy note
  in section 5.
- **Pool exhaustion during backfill.** DECIDED, see the fallback note in section 5.
  Never occurred in the full run.
- **Gate never fires on a too-diverse corpus.** Not a bug in the method, but it makes
  results look flat. Handled at the dataset level, see IMPLEMENTATION_PLAN.md. On the
  chosen corpus the gate fires on 24 percent of queries at k = 3, so this did not
  happen.
- **Ties in relevance ordering.** DECIDED: sort by relevance descending, break ties by
  chunk id ascending, using a stable sort. This applies everywhere an ordering is
  taken: pool ordering, plain top-k, the dedup keep/drop choice, and backfill order.
  Runs are then reproducible.
