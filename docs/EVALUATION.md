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
> the method's own rule, which a reviewer would rightly call circular. What replaced it
> is not a new metric but a better way to report metrics 1 to 4: every number is split
> into tripped and not-tripped queries (Reporting guidance below) and shown in the five
> core graphs, with the raw numbers in `results/`.

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

## Query set (DECIDED)

Stored in `data/queries.json`, 100 queries.

1. **How many: 100.** Enough for a steady trigger rate, small enough for the team to
   read every one.
2. **Who writes them: Claude, in-session, then the team reviews.** No API or extra tool.
   The team reads all 100 and fixes or drops bad ones. Viva line: "generated by an LLM
   from the corpus, reviewed by hand".
3. **What kind: 50 narrow plus 50 broad.**
   - Narrow: 50 chunk ids drawn with `random.Random(0).sample(range(136), 50)`. One
     question per chunk, aimed at a specific fact in that chunk. Each narrow query
     records its `source_chunk`.
   - Broad: 50 questions on topics covered by at least two of the three articles, judged
     from their section headings (symptoms, complications, causes, pathophysiology,
     diagnosis, prevention, management, epidemiology, history, research). Each records
     its `topic`.
   - The broad/narrow ratio partly sets the trigger rate, so results are reported per
     group as well as overall. Nobody can then say the ratio was tuned to flatter the
     gate.
4. **No calibration split.** delta and tau come from the corpus and the chunk
   pseudo-queries (METHOD.md sections 4 and 5), never from these queries, so all 100
   are used for evaluation only.

**Freeze rule (a strong default, not set in stone).** Commit the queries before the
first evaluation run and avoid editing them after seeing results. If a change is ever
unavoidable, it is a last resort, and the change and the reason go in this section.

## Graphs (DECIDED, the core set)

The graphs are the main deliverable of the evaluation, more than the tables. Each one
carries one message. The data behind every graph is also saved as a CSV in `results/`,
so any plot can be redrawn and checked.

1. **Cost per query.** Bar chart, one bar each for plain, MMR, and gate: average
   similarity comparisons per query across the whole query set. Message: the gate
   costs a fraction of MMR. This is the headline.
2. **Cost as k grows.** Line chart, k = 3, 5, 10, 15 on the x-axis, average comparisons on
   the y-axis, one line per method. Message: MMR's cost grows quickly with k while the
   gate stays small on queries that do not trip, so the gap widens. It answers "at
   k = 3 the saving is only microseconds". tau is re-derived for each k with the
   formula in METHOD.md section 4.
3. **Where queries fall.** Histogram of the gate signal, one value per query (the mean
   pair similarity of its plain top-k). X-axis is the signal, measured 0.686 to 0.869, in
   bins about 0.01 wide. Y-axis is the number of queries. A vertical line at tau.
   Bars left of the line in one colour (shipped as-is, cost C(k,2) lookups), bars to
   the right in another (tripped, repaired), each side labelled with its share of
   queries. Message: most queries need nothing, and only the tail on the right ever
   needed MMR's work. Optional faint marker at b to show tau sits just above a normal
   top-k. Leave it off the slide version.
4. **Tripped vs not tripped.** Dot plot, two panels (ILS, relevance), one row per
   group of queries, one dot per method with its value printed beside it. Message:
   where the gate trips it lands between plain and MMR; where it does not, it sits
   exactly on plain while MMR still moves away, at many times the cost. On this data MMR
   does gain a little diversity on not-tripped queries (ILS 0.773 to 0.745 at k=3) for
   a small relevance loss, so do not claim it gains nothing.
   **DECIDED: dot plot, not bars.** The averages differ only in the second or third
   decimal, so bars from zero all look the same height, and bars on a cut axis would
   exaggerate the gaps. A dot is read by position, so a zoomed axis is honest. The axis
   is shared by both groups so gaps compare directly.
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

Produced by `uv run python evaluation/make_graphs.py`. The evaluation code lives in its
own `evaluation/` folder, separate from the method in `src/`.

## Results (the full run)

All 100 queries, k = 3, pool 15, delta = 0.856, tau = 0.806 (computed on the fly; the
docs round it to 0.807 from the rounded b, the CSVs keep the unrounded value), MMR
lambda = 0.7. Numbers are copied from `results/summary.csv` and
`results/cost_vs_k.csv`. If anything is rerun, refresh this section from those files
rather than editing numbers by hand.

### The headline

> On average the gate method spends **4.26 similarity comparisons per query, against
> 40 for always-on MMR** (about 11 percent of MMR's cost), at a **24 percent trigger
> rate**. On the 24 queries that trip, ILS falls from 0.825 to 0.795 while relevance
> moves only from 0.729 to 0.724. On the 76 that do not trip, the gate returns plain
> top-k exactly, while MMR still changed 47 of them at the full 40 comparisons each.

### Metrics 1 and 2: trigger rate and compute cost

| Method | Avg comparisons per query | Trigger rate |
| --- | --- | --- |
| Plain top-k | 0 | n/a |
| MMR | 40.0 | n/a (runs on every query) |
| Gate | 4.26 | 24% (24 of 100) |

The gate's 4.26 breaks down as 3 on each of the 76 queries that did not trip and 8.25
on average on the 24 that did (3 for the gate plus 5.25 in repair).

Cost as k grows (graph 2). tau is re-derived for every k.

| k | tau | MMR | Gate | Gate as share of MMR | Trigger rate |
| --- | --- | --- | --- | --- | --- |
| 3 | 0.806 | 40 | 4.26 | 11% | 24% |
| 5 | 0.780 | 220 | 18.41 | 8% | 46% |
| 10 | 0.760 | 1,965 | 91.42 | 5% | 44% |
| 15 | 0.749 | 6,860 | 224.58 | 3% | 43% |

### Metrics 3 and 4: ILS and relevance

| Queries | Method | ILS (lower is better) | Relevance | Changed vs plain |
| --- | --- | --- | --- | --- |
| All 100 | Plain | 0.786 | 0.714 | 0% |
| | MMR | 0.752 | 0.709 | 65% |
| | Gate | 0.778 | 0.713 | 15% |
| Tripped (24) | Plain | 0.825 | 0.729 | 0% |
| | MMR | 0.774 | 0.722 | 75% |
| | Gate | 0.795 | 0.724 | 63% |
| Not tripped (76) | Plain | 0.773 | 0.709 | 0% |
| | MMR | 0.745 | 0.705 | 62% |
| | Gate | 0.773 | 0.709 | 0% |

Broad and narrow queries behave alike: trigger rate 26 percent on broad, 22 percent on
narrow, and the same ordering of the three methods in both groups. The query mix is
therefore not what drives the result.

### Honest weak spots (say these in the writeup and the viva)

- **MMR diversifies more than the gate.** On tripped queries MMR cuts ILS by 0.051,
  the gate by 0.030, so the gate gets about 60 percent of MMR's diversity gain there,
  for about 21 percent of its cost (8.25 versus 40 comparisons). Over all 100 queries
  the gate gets about 22 percent of MMR's ILS reduction. This matches the pitch in
  METHOD.md section 2: comparable quality where it is needed, at a fraction of the
  cost, not "beats MMR". Per query, the gate's ILS is at or below MMR's on 11 of the 24
  tripped queries (9 of those are the same set).
- **9 of the 24 tripped queries came out unchanged.** Their mean was above tau but no
  single pair was above delta, so dedup had nothing to drop and the 3 dedup lookups
  bought nothing. This is the accepted gate and repair mismatch in METHOD.md section 5,
  now measured. It is why only 15 percent of queries changed overall.
- **MMR on not-tripped queries is not pure waste.** It does lower ILS (0.773 to 0.745)
  for a small relevance cost (0.709 to 0.705). The argument is that this gain is small
  and the 40 comparisons are paid on every one of those 76 queries, not that MMR gains
  nothing.
- **The trigger rate is not constant across k.** It roughly doubles from k = 3 (24
  percent) to k = 5 (46 percent) and then stays near 44 percent. The tau formula keeps
  the meaning of tau the same for every k, not the trigger rate. The cost saving still
  widens with k, because MMR's cost grows much faster than the gate's.
- **The relax fallback never fired**, at any of k = 3, 5, 10, 15. Pool exhaustion is a
  real edge case in the code but did not occur on this corpus and query set.
- The absolute differences are small (second or third decimal), because BGE's high
  similarity floor compresses every score into roughly 0.65 to 0.90. Graph 4 uses a
  dot plot for exactly this reason.

Downstream answer quality (metric 6, stretch) was not run.
