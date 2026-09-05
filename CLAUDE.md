# CLAUDE.md - Redundancy-Gated Retrieval for RAG

## What this project is

Standard RAG retrieves the top-k chunks most similar to a query. Those chunks are
often near-duplicates of each other, which wastes the LLM's context window on
repeated information instead of complementary evidence. The established fix is
Maximal Marginal Relevance (MMR), which re-ranks a candidate pool to trade off
relevance against diversity. The problem with MMR and its descendants is that they
run diversification on **every single query**, including the many whose top-k is
already diverse and needs no correction.

This project proposes a **lightweight redundancy gate**: a cheap check that fires a
repair step only when the top-k is actually redundant, and otherwise ships the plain
top-k untouched with zero extra work. The contribution is **efficiency under a
realistic query distribution**, not beating MMR on quality.

Project title: Redundancy-Gated Retrieval: Optimized Diversification of RAG Context.

## Context you need before writing any code

- 7th semester CS group project, three students, all beginners to RAG (mostly
  exposed to simple/vanilla RAG so far). They are juggling placement preparation, so
  the project must stay small and finishable.
- The realistic goal is to clear project reviews with an honest, well-executed
  incremental contribution. Not to publish, not to file the patent the college keeps
  mentioning.
- Keep code, comments, and any generated explanation at a simple-to-moderate
  technical level unless explicitly asked for more depth.
- The work has to be defensible in a viva. Every step should be inspectable and
  explainable by a beginner.

## Tech stack (decided, do not swap without asking)

- Plain Python. No LangChain or LlamaIndex for the core pipeline. The contribution
  lives in the gate and repair logic, which needs precise control over the pool, the
  similarity matrix, and backfill order. A framework would hide exactly the parts a
  reviewer will ask about.
- Embeddings: `sentence-transformers`, model **BAAI/bge-base-en-v1.5**. Not
  bge-large (marginal gain, slower to iterate for three people on limited compute).
- Retrieval: `faiss` is fine, but for a corpus this small (see IMPLEMENTATION_PLAN.md)
  plain numpy cosine similarity is acceptable and easier to explain.
- Similarity matrix and metrics: numpy / scikit-learn.
- Evaluation: a small custom harness. Off-the-shelf RAG eval tools (RAGAS and
  friends) are built around faithfulness and answer relevance, not diversity, so they
  do not cover what this project measures.

## How the documentation is organized

- **docs/METHOD.md** - the method itself. FIXED. Pipeline, gate, repair, backfill,
  MMR baseline, the worked example, and known edge cases.
- **docs/EVALUATION.md** - the evaluation criteria. FIXED. Every metric with its
  formula and worked-example numbers, plus the importance ranking.
- **docs/IMPLEMENTATION_PLAN.md** - stack detail, staged build order, the definition
  of the 70% milestone, suggested repo layout, function signatures, and the config
  schema.
- **docs/CHECKLIST.md** - short status board. Read this first, it is the fastest way
  to see which stage the build is on and which decisions are settled or still open.
- **docs/FORMULAS.md** - one page reference sheet of every formula in the project, each
  with its symbols and a checkable number from the worked example.

## Operating rules (important)

1. **Flag anything that looks like a decision. Do not assume your way past it.** This
   is the single most important behavior expected of you here. Many parameters, rules,
   and design choices in this project are still under deliberation, and the team may
   not have noticed all of them yet. Your job is to act as a second set of eyes:
   whenever implementing something forces a choice that is not explicitly pinned down
   in METHOD.md or EVALUATION.md, stop and raise it before writing it into logic.

   This covers the obvious knobs (how tau and delta are set, whether the gate signal
   is a simple mean or a weighted average) but, more importantly, the subtler things
   the team may have overlooked entirely: tie-breaking order in relevance ranking,
   what happens when backfill runs out of candidates, how multi-way redundancy (three
   or more mutually similar chunks) is resolved rather than isolated pairs, whether
   embeddings are normalized, whether chunk-to-chunk similarity uses the same space as
   query-to-chunk, what the backfill acceptance check actually tests against, and so
   on. The threshold question is only one example of the kind of push-back wanted, not
   the boundary of it. When in doubt about whether something is settled, assume it is
   not and ask.

   When you hit one of these: state the choice plainly, lay out the options, give a
   recommendation with your reasoning, and ask before committing to it. If you must
   produce running code before the team decides, wire the choice to a config knob,
   pick a clearly-labeled interim default, and leave a visible `# NEEDS DECISION:`
   comment explaining the tradeoff. A silent default baked into logic, where the team
   never learns a choice was even made, is the one outcome to avoid.

   Once a decision is settled, write it back into the relevant doc as a **DECIDED**
   note with the reasoning, and update docs/CHECKLIST.md. A settled decision should
   never have to be re-argued from memory.
2. **The method and the evaluation criteria are fixed.** Do not redesign them. If you
   spot a genuine problem, flag it and wait, do not quietly "fix" it in code.
3. **Every knob is a config parameter.** tau, delta, k, pool size, lambda (for the
   MMR baseline), similarity metric, embedding model. Nothing hardcoded inline.
4. Prefer inspectable, boring code over clever abstractions. This has to survive a
   viva.
5. Writing style for any generated text, comments, or docs: natural language, and do
   not use em dashes or en dashes.
