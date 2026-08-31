# EVALUATION.md - Evaluation Criteria (FIXED)

These metrics and their relative importance are settled. Implement all of them in the
eval harness. Compute every metric for all three methods (plain top-k, full MMR, gate
method) on the same query set so the three are directly comparable.

Off-the-shelf RAG eval tools center on faithfulness and answer relevance, not
diversity, so a small custom harness is required. Instrument the methods to **count
the actual similarity comparisons performed** rather than estimating cost from a
formula. Counted comparisons are more defensible in a viva than a derived number.

Throughout, "similarity" means the same cosine similarity in the same embedding space
used by the retriever. All worked-example numbers below come from the fixture in
METHOD.md (plain top-3 = {A, B, C}, gate and MMR output = {A, C, D}, delta = 0.8).

---

## Metric 1 and 2 (bundled): Gate trigger rate + Compute cost

**These two are the contribution and cannot be read apart.** Trigger rate says how
often the expensive work is skipped. Compute cost turns that into the actual saving.
Reported alone, a trigger rate is meaningless until compute cost shows what it buys.

**Gate trigger rate.** The fraction of queries on which the gate signal exceeds `tau`,
so the repair step actually runs.

    trigger_rate = (queries where gate tripped) / (total queries)

Example: gate fires on 40 of 200 queries, trigger rate = 20 percent. That means 80
percent of queries paid only the fixed C(k,2) gate cost and nothing more, while
always-on MMR would have run its full re-ranking on all 200.

**Compute cost.** The average number of similarity comparisons performed per query,
measured across the whole query set (not only the queries where the gate fired), for
each method.

- Gate method per query = C(k,2) for the gate, plus the comparisons spent in repair on
  the queries that tripped, plus zero on the queries that did not.
- MMR per query = the comparisons its round-by-round rescoring performs, which is
  effectively flat and paid on every query.

Report both as averages, and report them together. The headline result is a sentence
of the form "average X comparisons per query for the gate method versus Y for
always-on MMR, at a Z percent trigger rate."

Direction: lower compute cost is better, at a given quality (see metrics 3 and 4).

## Metric 3 and 4 (bundled): Intra-list similarity + Relevance preservation

**These two prove the method works and must be viewed as a pair.** ILS alone is
gameable, since k unrelated chunks score a near-zero ILS while being useless for the
query. The claim is the paired movement: ILS drops a lot while relevance barely moves.

**Intra-list similarity (ILS).** The mean pairwise chunk-to-chunk similarity within the
final returned set. **Minimize** it. Lower ILS means less redundancy, so the k slots
carry more distinct evidence.

    ILS = mean of pairwise similarities among the final k chunks

Worked example: plain top-3 {A, B, C} has ILS = (0.85 + 0.30 + 0.35) / 3 = 0.50. After
repair, {A, C, D} has ILS = (0.30 + 0.25 + 0.30) / 3 = 0.283. The drop from 0.50 to
0.283 is the diversity gain.

**Relevance preservation.** The mean query-to-chunk similarity of the final set.
Report it right next to ILS. The point is to show diversity was gained without
meaningfully hurting relevance.

    relevance = mean of query-to-chunk similarities over the final k chunks

Worked example: plain top-3 {A, B, C} = (0.90 + 0.88 + 0.86) / 3 = 0.88. After repair,
{A, C, D} = (0.90 + 0.86 + 0.80) / 3 = 0.853. A small, expected dip: a redundant but
relevant chunk (B) was swapped for a non-redundant but slightly less relevant one (D).

The defensible claim is that this dip is small and comparable to what MMR pays for the
same diversity gain, so always compute both ILS and relevance for MMR too and put the
three methods side by side.

## Metric 5: Duplicate reduction

Supporting evidence, and more intuitive for a non-technical committee than ILS. It is
a coarser restatement of the same redundancy story, which is why it ranks below the
ILS-plus-relevance pair rather than beside it.

**Duplicate rate.** The fraction of chunk pairs in the final set whose similarity
exceeds `delta`.

    duplicate_rate = (pairs above delta) / C(k,2)

Worked example: plain top-3 has 1 over-delta pair (A-B at 0.85, delta = 0.8) out of 3
pairs, so 33 percent. After repair, {A, C, D} has zero pairs above delta, so 0
percent. Averaged over the query set this becomes a line like "near-duplicate pairs
fell from 18 percent of top-k pairs to 2 percent."

Direction: lower is better.

## Metric 6: Downstream answer quality (STRETCH, optional)

Nice to have, not required to defend the core claim. Use an LLM as a judge on a small
handful of queries to check that diversification does not break answer generation. It
is noisy, slow, and not part of the central efficiency argument. Do this only if time
allows, and never at the expense of getting metrics 1 through 5 solid across the full
dataset.

---

## Importance ranking (what to focus on)

1. **Gate trigger rate + Compute cost (bundled).** The whole thesis. This is what a
   reviewer judges the contribution on.
2. **ILS + Relevance preservation (bundled).** Proves the method actually works, as a
   pair, not in isolation.
3. **Duplicate reduction.** Supporting, committee-friendly restatement of the
   redundancy story.
4. **Downstream answer quality.** Stretch goal only. Skip if time is tight.

## Reporting guidance

- Put the three methods (plain top-k, MMR, gate) in one comparison table covering ILS,
  relevance, duplicate rate, trigger rate (gate only), and average compute cost.
- Include a small **sensitivity sweep over `tau`**: a few values from strict to loose,
  showing where trigger rate lands and how ILS, relevance, and cost move with it. This
  demonstrates `tau` is doing real work rather than being one lucky pick, and directly
  addresses the open `tau`-setting question in METHOD.md.
- Report averages across the full query set, and keep the per-query raw numbers so a
  reviewer can spot-check.
- If the gate underperforms MMR on some queries, or barely fires on a too-diverse
  corpus, report it plainly. An honest weak spot is more credible than results that
  look perfect everywhere.
