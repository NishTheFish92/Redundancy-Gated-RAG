# FORMULAS.md - every formula in the project, in one place

A quick reference sheet. Each entry gives the formula, what the symbols mean, and a
number from the METHOD.md worked example so you can check your implementation against
something. The worked example uses a pool of 6 chunks (A to F) with k = 3, delta = 0.8,
tau = 0.35, lambda = 0.7.

Reminder: those example values are synthetic. See the note in METHOD.md section 7.

---

## Notation

| Symbol | Meaning |
| --- | --- |
| `n` | number of chunks in the corpus (currently 136) |
| `d` | embedding dimensions (768 for bge-base) |
| `E` | embedding matrix, shape `(n, d)`, one chunk per row |
| `S` | similarity matrix, shape `(n, n)` |
| `q` | the query embedding, length `d` |
| `k` | how many chunks are returned (config, currently 3) |
| `tau` | gate threshold, the "this set is too redundant" line (0.807 at k = 3, formula 15) |
| `delta` | duplicate threshold, the "these two are the same" line (0.856, formula 14) |
| `lambda` | MMR relevance versus diversity weight (0.7) |
| `b` | typical similarity of two non-duplicate chunks in the same top-k (0.782 at k = 3) |

---

## 1. L2 normalization

Rescale a vector to length 1, keeping its direction.

```
v_normalized = v / ||v||           where  ||v|| = sqrt(v1^2 + v2^2 + ... + vd^2)
```

Example: `v = [3, 4]`, `||v|| = sqrt(9 + 16) = 5`, so `v_normalized = [0.6, 0.8]`.

Applied to every chunk and every query. It is what makes formula 2 valid.

## 2. Cosine similarity

```
cosine(a, b) = (a . b) / (||a|| * ||b||)

and if both are normalized (||a|| = ||b|| = 1) this collapses to

cosine(a, b) = a . b = a1*b1 + a2*b2 + ... + ad*bd
```

Range is -1 to 1. Higher means more similar. Because everything is normalized, the
project only ever computes the dot product.

Example: `[0.6, 0.8] . [0.8, 0.6] = 0.48 + 0.48 = 0.96`.

## 3. Similarity matrix

Every chunk-to-chunk similarity, computed once and cached.

```
S = E @ E.T                        shape (n, n)

S[i][j] = similarity of chunk i and chunk j
```

`S` is symmetric and its diagonal is 1. After this, one similarity comparison means one
lookup in `S`, which is what makes the compute cost countable rather than estimated.

## 4. Query relevance

How well each chunk matches the query.

```
relevance = E @ q                   shape (n,)

relevance[i] = similarity of chunk i to the query
```

The query is embedded with the BGE instruction prefix, chunks are not. Sort descending,
break ties by chunk id ascending, take the top `pool_size` as the pool and the top `k` of
those as the plain top-k.

```
pool_size = k * pool_multiplier     (5, so k=3 -> 15 and k=5 -> 25)
```

## 5. Number of pairs in a set

```
C(k, 2) = k * (k - 1) / 2
```

k=3 gives 3 pairs, k=5 gives 10. This is the fixed cost of the gate on every query.

## 6. Gate signal

Mean pairwise similarity inside the current top-k.

```
signal = ( sum of S[i][j] over all pairs i < j in top-k ) / C(k, 2)
```

Worked example, top-3 is {A, B, C} with A-B 0.85, A-C 0.30, B-C 0.35:

```
signal = (0.85 + 0.30 + 0.35) / 3 = 0.50
```

DECIDED: simple mean. See METHOD.md section 4.

## 7. Gate trip test

```
gate trips  if  signal > tau
ships as is if  signal <= tau
```

Worked example: `0.50 > 0.35`, so the gate trips.

## 8. Duplicate test (dedup)

Two chunks are duplicates when

```
S[i][j] > delta
```

Drop the lower-relevance member of the pair. Worked example: A-B is 0.85 which is above
delta 0.8, and B has lower relevance than A, so B is dropped.

DECIDED: when three or more chunks are mutually similar, drop one chunk at a time
(the worst pair first, then recheck). A backfill candidate is rejected if `S[c][p] >
delta` for any kept chunk `p`. See METHOD.md section 5.

## 9. MMR score (baseline)

At every round, for each remaining candidate `c`:

```
score(c) = lambda * relevance(c) - (1 - lambda) * max( S[c][p] for p in already_picked )
```

Pick the highest scorer, add it to `already_picked`, repeat until k are chosen. Round 1
has an empty picked set, so it reduces to picking the most relevant chunk.

Worked example with lambda 0.7: round 1 picks A, round 2 picks C (B loses because it is
too similar to A), round 3 picks D.

---

# Evaluation metrics

## 10. Gate trigger rate

```
trigger_rate = (queries where the gate tripped) / (total queries)
```

Example: 40 of 200 queries gives 20 percent, meaning 80 percent of queries paid only
the C(k,2) gate cost.

## 11. Compute cost

Average similarity comparisons per query, counted rather than derived, across the whole
query set including the queries that did not trip.

```
cost_gate_method = mean over queries of ( C(k,2) + comparisons spent in repair )
cost_mmr         = mean over queries of ( comparisons spent in re-ranking )
```

Repair contributes 0 on a query that did not trip. Report this next to the trigger rate,
neither number means anything alone.

## 12. Intra-list similarity (ILS)

Mean pairwise similarity of the final returned set. Lower is better.

```
ILS = ( sum of S[i][j] over all pairs i < j in the final set ) / C(k, 2)
```

Same formula as the gate signal, applied to the final output instead of the plain top-k.

Worked example: {A, B, C} gives 0.50, and after repair {A, C, D} gives
`(0.30 + 0.25 + 0.30) / 3 = 0.283`.

## 13. Relevance preservation

Mean query-to-chunk similarity of the final set. Should barely move. Always report it
beside ILS, since ILS on its own is gameable by returning unrelated chunks.

```
relevance_preserved = ( sum of relevance[i] for i in the final set ) / k
```

Worked example: {A, B, C} gives `(0.90 + 0.88 + 0.86) / 3 = 0.88`, and {A, C, D} gives
`(0.90 + 0.86 + 0.80) / 3 = 0.853`.

---

# Calibration (how delta and tau are set)

Both run offline in `scripts/calibrate.py` and are pinned in config.yaml. Full reasoning
in METHOD.md sections 4 and 5.

## 14. Duplicate threshold (delta)

For every chunk `i`, build a fake duplicate `f_i` that keeps 75 percent of its sentences
and replaces the rest with sentences from a chunk on another page. Then

```
delta = mean over seeds 0..4 of  p5( cosine(f_i, chunk_i) for every chunk i )
```

`p5` is the 5th percentile. When 75 percent of a chunk is not a whole number of
sentences, round at random: for 7 sentences (5.25) keep 5 with probability 0.75 and 6
with probability 0.25.

Current numbers: per-seed p5 values 0.861, 0.849, 0.861, 0.858, 0.854, mean **0.856**.

## 15. Gate threshold (tau)

```
tau = ( delta + (C(k,2) - 1) * b ) / C(k,2)
```

The gate signal of a top-k holding one pair at `delta` and every other pair at `b`.
`b` is the median of all pseudo-query top-k pair similarities at or below `delta`, where
each chunk stands in as a query and is excluded from its own top-k.

Current numbers, k = 3: `(0.856 + 2 * 0.782) / 3 = 0.807`. At k = 5, `b` = 0.772 and
`tau = (0.856 + 9 * 0.772) / 10 = 0.780`.

---

## The headline result these build to

> average X comparisons per query for the gate method versus Y for always-on MMR, at a
> Z percent trigger rate, with ILS falling from P to Q while relevance moves only from
> R to T.
