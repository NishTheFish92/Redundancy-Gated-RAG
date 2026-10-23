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

## Metric 5: Duplicate reduction (REMOVED)

> **DECIDED: dropped.** It counted pairs in the final set above `delta`. The gate
> method's repair removes exactly those pairs using the same `delta`, so on every query
> where repair ran the gate scored 0 percent by construction. It graded the method with
> the method's own rule, which a reviewer would rightly call circular. Replacement
> metrics that show real differences between the three methods, with outputs written to
> a `results/` folder, are still to be designed. See docs/CHECKLIST.md.

## Metric 6: Downstream answer quality (STRETCH, optional)

Nice to have, not required to defend the core claim. Use an LLM as a judge on a small
handful of queries to check that diversification does not break answer generation. It
is noisy, slow, and not part of the central efficiency argument. Do this only if time
allows, and never at the expense of getting metrics 1 through 4 solid across the full
dataset.

---

## Importance ranking (what to focus on)

1. **Gate trigger rate + Compute cost (bundled).** The whole thesis. This is what a
   reviewer judges the contribution on.
2. **ILS + Relevance preservation (bundled).** Proves the method actually works, as a
   pair, not in isolation.
3. **Downstream answer quality.** Stretch goal only. Skip if time is tight.

## Reporting guidance

- Put the three methods (plain top-k, MMR, gate) in one comparison table covering ILS,
  relevance, trigger rate (gate only), and average compute cost.
- **Deferred for now: a small sensitivity sweep over `tau`**, a few values from strict
  to loose, showing where trigger rate lands and how ILS, relevance, and cost move with
  it. It would demonstrate `tau` is doing real work rather than being one lucky pick.
- **DECIDED, deferred for now: also sweep `delta`** (for example 0.82 to 0.92). Left
  out of the core graph set below for now, kept here so the reasoning is not lost. Because tau is derived
  from delta (METHOD.md section 4), each delta value comes with its own tau, so this is
  one sweep axis that moves both. It shows how ILS, relevance, and cost
  respond to the definition of "duplicate". The sweep is a sensitivity analysis only:
  delta is set by the calibration rule, never by picking the value with the best
  results, which would be tuning on the test set.
- Report averages across the full query set, and keep the per-query raw numbers so a
  reviewer can spot-check.
- If the gate underperforms MMR on some queries, or barely fires on a too-diverse
  corpus, report it plainly. An honest weak spot is more credible than results that
  look perfect everywhere.
- **DECIDED: split results into tripped and not-tripped queries.** Averages over the
  whole query set hide the story, because the gate only changes the minority of
  queries that trip. On tripped queries, compare how much each method reduced ILS and
  what it cost in relevance. On not-tripped queries, the gate is identical to plain
  top-k by design, so the question is how often MMR changed an already-fine set and how
  much relevance that cost. That second group is the thesis: always-on MMR does work,
  and gives up relevance, on queries that never needed it.

## Graphs (DECIDED, the core set)

The graphs are the main deliverable of the evaluation, more than the tables. Each one
carries one message. The data behind every graph is also saved as a CSV in `results/`,
so any plot can be redrawn and checked.

1. **Cost per query.** Bar chart, one bar each for plain, MMR, and gate: average
   similarity comparisons per query across the whole query set. Message: the gate
   costs a fraction of MMR. This is the headline.
2. **Cost as k grows.** Line chart, k = 3, 5, 10 on the x-axis, average comparisons on
   the y-axis, one line per method. Message: MMR's cost grows quickly with k while the
   gate stays small on queries that do not trip, so the gap widens. It answers "at
   k = 3 the saving is only microseconds". tau is re-derived for each k with the
   formula in METHOD.md section 4.
3. **Where queries fall.** Histogram of the gate signal, one value per query (the mean
   pair similarity of its plain top-k). X-axis is the signal, roughly 0.68 to 0.88, in
   bins about 0.01 wide. Y-axis is the number of queries. A vertical line at tau.
   Bars left of the line in one colour (shipped as-is, cost C(k,2) lookups), bars to
   the right in another (tripped, repaired), each side labelled with its share of
   queries. Message: most queries need nothing, and only the tail on the right ever
   needed MMR's work. Optional faint marker at b to show tau sits just above a normal
   top-k. Leave it off the slide version.
4. **Tripped vs not tripped.** Grouped bars of ILS and relevance for each method,
   shown separately for the two groups of queries. Message: on queries that were
   already fine, MMR changes things for no gain.
5. **ILS vs relevance.** Scatter, one dot per query per method. Message: the gate
   removes redundancy without losing relevance.

Considered and left out for now: a delta sweep graph (see above), agreement between
the gate and MMR (shared chunks on tripped queries), and wall-clock time per query
(real but noisy at this corpus size).

## results/ folder (DECIDED)

- `results/per_query.csv`: one row per query and method, with every number, for
  spot-checking.
- `results/summary.csv`: the three-method comparison table, also split into tripped
  and not-tripped.
- `results/cost_vs_k.csv`: the data for graph 2.
- `results/figures/`: the five graphs.
