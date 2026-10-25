// Builds paper/paper.docx from the text below and the figures in results/figures/.
//
//   cd paper && npm install && node build_paper.js
//
// Figures are read from results/figures/, written by evaluation/make_graphs.py.
// Inline markup in body text: *italic* and **bold**.

const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell,
  AlignmentType, WidthType, BorderStyle, LevelFormat, TabStopType, Footer,
  PageNumber,
} = require("docx");

const FONT = "Times New Roman";
const BODY = 22;              // half-points, 11 pt
const PAGE_W = 11906;         // A4 in DXA
const PAGE_H = 16838;
const MARGIN = 1440;
const TEXT_W = PAGE_W - 2 * MARGIN;
const TEXT_W_PX = Math.round((TEXT_W / 1440) * 96);

// ---------- helpers ----------

function runs(text, base = {}) {
  // Split on **bold** and *italic* markers.
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(new TextRun({ text: tok.slice(2, -2), bold: true, ...base }));
    else out.push(new TextRun({ text: tok.slice(1, -1), italics: true, ...base }));
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}

const p = (text) => new Paragraph({
  children: runs(text),
  alignment: AlignmentType.JUSTIFIED,
  spacing: { after: 120, line: 264 },
});

const h1 = (text) => new Paragraph({
  children: [new TextRun({ text, bold: true, size: 24 })],
  spacing: { before: 240, after: 120 },
  keepNext: true,
});

const h2 = (text) => new Paragraph({
  children: [new TextRun({ text, bold: true, italics: true })],
  spacing: { before: 160, after: 80 },
  keepNext: true,
});

const item = (text, ref) => new Paragraph({
  children: runs(text),
  numbering: { reference: ref, level: 0 },
  alignment: AlignmentType.JUSTIFIED,
  spacing: { after: 60, line: 264 },
});

// Centered equation with its number flush right.
const eq = (text, num) => new Paragraph({
  tabStops: [
    { type: TabStopType.CENTER, position: Math.round(TEXT_W / 2) },
    { type: TabStopType.RIGHT, position: TEXT_W },
  ],
  children: [new TextRun({ text: "\t" + text, italics: true }), new TextRun({ text: `\t(${num})` })],
  spacing: { before: 60, after: 120 },
});

const caption = (label, text) => new Paragraph({
  children: [new TextRun({ text: label + " ", bold: true, size: 20 }), ...runs(text, { size: 20 })],
  alignment: AlignmentType.JUSTIFIED,
  keepNext: label.startsWith("Table"),
  spacing: { before: 60, after: 200 },
});

function figure(file, widthFraction) {
  const buf = fs.readFileSync(path.join(__dirname, "..", "results", "figures", file));
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
  const width = Math.round(TEXT_W_PX * widthFraction);
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    keepNext: true,
    spacing: { before: 120, after: 0 },
    children: [new ImageRun({
      type: "png", data: buf,
      transformation: { width, height: Math.round(width * h / w) },
    })],
  });
}

const LINE = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
const NONE = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };

// Three-rule table (top, under header, bottom), the usual plain academic style.
function table(header, rows, colWidths) {
  const total = colWidths.reduce((a, b) => a + b, 0);
  const cell = (text, i, { bold = false, top = NONE, bottom = NONE, last = false } = {}) => new TableCell({
    width: { size: colWidths[i], type: WidthType.DXA },
    borders: { top, bottom, left: NONE, right: NONE },
    margins: { top: 40, bottom: 40, left: 100, right: 100 },
    children: [new Paragraph({
      keepNext: !last,
      alignment: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER,
      children: [new TextRun({ text, bold, size: 20 })],
    })],
  });
  const head = new TableRow({
    tableHeader: true,
    children: header.map((t, i) => cell(t, i, { bold: true, top: LINE, bottom: LINE })),
  });
  const body = rows.map((r, ri) => new TableRow({
    children: r.map((t, i) => cell(t, i, { bottom: ri === rows.length - 1 ? LINE : NONE, last: ri === rows.length - 1 })),
  }));
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: colWidths,
    alignment: AlignmentType.CENTER,
    rows: [head, ...body],
  });
}

const ref = (text) => new Paragraph({
  children: runs(text, { size: 20 }),
  indent: { left: 400, hanging: 400 },
  spacing: { after: 80 },
});

// ---------- content ----------

const title = [
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 200 },
    children: [new TextRun({ text: "Redundancy-Gated Retrieval: Optimized Diversification of RAG Context", bold: true, size: 32 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 60 },
    children: [new TextRun({ text: "Nishant Ajit, Jeevaanandh Vi, Pratyush Kumar V", size: 24 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "School of Computer Science and Engineering (SCOPE)", italics: true })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 360 },
    children: [new TextRun({ text: "Vellore Institute of Technology", italics: true })],
  }),
];

const abstract = [
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 120, line: 264 },
    indent: { left: 567, right: 567 },
    children: [
      new TextRun({ text: "Abstract. ", bold: true }),
      ...runs("Retrieval-augmented generation (RAG) passes the k chunks most similar to a query to a language model, and because these chunks are often near-duplicates of each other, part of the context window repeats the same evidence. Maximal Marginal Relevance (MMR) reduces this redundancy by re-ranking a candidate pool, but it does so on every query, including queries whose top-k is already diverse. We propose a redundancy gate that computes the mean pairwise similarity of the plain top-k and, only when that mean exceeds a threshold, runs a repair step that drops near-duplicate chunks and backfills the freed slots from a larger pool. Both thresholds are derived from the corpus by a fixed rule, without using the evaluation queries. On 100 queries over three overlapping Wikipedia articles on diabetes, the gate tripped on 24% of queries at k = 3 and used 4.26 similarity comparisons per query on average, against 40 for always-on MMR. On tripped queries it lowered intra-list similarity from 0.825 to 0.795 while mean relevance moved from 0.729 to 0.724. MMR reduced redundancy further, to 0.774, at a higher cost. In our setting the cost gap widens with k, and at k = 15 the gate used about 3% of MMR's comparisons."),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 240 },
    indent: { left: 567, right: 567 },
    children: [
      new TextRun({ text: "Keywords. ", bold: true }),
      new TextRun("retrieval-augmented generation, maximal marginal relevance, diversification, redundancy, dense retrieval"),
    ],
  }),
];

const intro = [
  h1("1. Introduction"),
  p("Retrieval-augmented generation grounds a language model in text retrieved at query time [6, 9]. A typical pipeline embeds the query, ranks corpus chunks by similarity to it, and keeps the top k. Because similarity to the query says nothing about similarity among the chunks themselves, a top-k drawn from several sources that describe the same fact can hold two or three restatements of it, leaving those slots without new evidence."),
  p("MMR [1] is the standard remedy. It builds the result one chunk at a time and penalizes candidates that resemble chunks already chosen, and later diversification methods likewise run on every query [2, 4, 5]. Many queries, however, return a top-k that is already diverse, and for those the re-ranking spends compute and may swap a relevant chunk for a less relevant one."),
  p("This paper makes diversification conditional. A cheap check, the gate, reads the C(k,2) pairwise similarities inside the plain top-k, which at k = 3 means three lookups. If their mean is at or below a threshold τ, the top-k is returned unchanged. Otherwise a repair step removes pairs above a duplicate threshold δ and refills the freed slots from a larger candidate pool. The contributions are as follows."),
  item("A redundancy gate and a threshold-based repair step that diversify only the queries that need it.", "contrib"),
  item("A rule that sets both thresholds from the corpus. δ comes from synthetic near-duplicates, and τ is derived from δ and k.", "contrib"),
  item("An evaluation that counts similarity comparisons in code and reports every metric separately for queries where the gate tripped and where it did not.", "contrib"),
  p("Our contribution is primarily one of efficiency, and MMR still achieves lower redundancy, as quantified in Section 5."),
];

const related = [
  h1("2. Related Work"),
  p("Carbonell and Goldstein introduced MMR to reduce redundancy in retrieval and summarization [1]. At each round it picks the candidate with the best combined score of relevance to the query and dissimilarity to the items already chosen. A weight λ sets the balance and has to be tuned by hand. MMR became the standard diversity method in information retrieval, and it re-ranks the full candidate pool on every query."),
  p("Later work broadened diversification. Vieira et al. proposed a framework to evaluate and optimize query result diversification, with two greedy methods, GMC and GNE, that gave more diverse results faster than earlier methods [2]. Drosou and Pitoura grouped diversity definitions into content, novelty and coverage based families [3], and later kept a diverse set updated over streaming data with a cover tree [4]. Zheng et al. reviewed diversification across databases, search, recommender systems and graphs, and named efficient query-time diversification as an open problem [5]. In each of these the diversification step always runs, with no check of whether the result is already diverse."),
  p("Studies of RAG show why redundant context matters. Surveys identify redundant and irrelevant retrieved content as a cause of poor output quality [6] and as a persistent limitation of current systems [9]. Huang et al. note that repetitive or irrelevant retrieved context can lead a RAG model to hallucinate [10]. Cuconasu et al. studied how the type of retrieved passage affects RAG accuracy [7], and Salemi and Zamani argued that a RAG retriever should be judged by how much it helps the generator, beyond relevance alone [8]. Agarwal et al. found that the same chunks are often retrieved across different queries and reused their computation through caching [11]. Together these works treat redundant retrieved content as an open problem for RAG, and the gate in this paper addresses the cost of correcting it."),
];

const method = [
  h1("3. Method"),
  h2("3.1 Overview"),
  p("Every embedding is L2-normalized, so cosine similarity equals the dot product. The chunk-to-chunk similarity matrix S = EEᵀ is computed once and cached, after which every chunk-to-chunk similarity is a single lookup in S. We count one lookup as one comparison, and all costs in this paper are given in comparisons. For a query q the pipeline runs four steps."),
  item("Retrieve a pool of the p = 5k chunks most similar to q. Ties in relevance are broken by chunk id.", "steps"),
  item("Split the pool into the plain top-k T and a reserve R that holds the remaining chunks in relevance order.", "steps"),
  item("Compute the gate signal on T. If it does not exceed τ, return T.", "steps"),
  item("Otherwise repair T using R and return the result.", "steps"),

  h2("3.2 The Gate"),
  p("The gate signal is the mean pairwise similarity inside the plain top-k."),
  eq("g(T) = Σ S(i, j) / C(k, 2),   over all pairs i < j in T", 1),
  p("The gate trips when g(T) > τ, and it costs C(k,2) comparisons on every query, which is 3 at k = 3 and 10 at k = 5. We also tried weighting each pair by the relevance of its members. Because relevance values inside a BGE top-k are nearly equal, for example 0.78, 0.76 and 0.75, the weighted signal barely differed from the plain mean, so we kept the plain mean."),

  h2("3.3 The Repair"),
  p("Repair has two stages. Dedup removes near-duplicates from T, and backfill refills the freed slots from R."),
  p("Dedup finds the most similar pair in the current set with S(i, j) > δ, drops the member with lower relevance, and then rechecks the smaller set, repeating until no pair exceeds δ. Removing one chunk at a time avoids over-pruning when three or more chunks are similar, since in a set where A-B and B-C exceed δ while A-C does not, dropping B alone resolves both pairs and keeps A and C, whereas a single pass would drop both B and C."),
  p("Backfill walks R in relevance order and accepts a candidate only if its similarity to every chunk already kept is at most δ. Rejected candidates are skipped, and each accepted chunk joins the kept set, so later candidates are checked against it too. The walk stops once the set is back to k chunks. If R runs out first, a fallback re-admits the rejected candidate least similar to the kept set until there are k chunks, which keeps the output size equal across methods so that their metrics compare fairly. The fallback was never needed in our experiments."),
  p("Repair is cheaper than MMR because of what it checks. MMR rescores every remaining candidate against every selected chunk in each round, whereas repair checks only the candidates it walks past, and only against the chunks it keeps. However, because repair relies on fixed thresholds with no continuous trade-off, its output can remain more redundant than MMR's."),

  h2("3.4 Choosing δ"),
  p("Thresholds picked by intuition do not transfer well to BGE. On our corpus unrelated text often scores between 0.6 and 0.7, and a typical pair inside a top-3 scores about 0.78, so both thresholds are derived from the corpus by a fixed rule."),
  p("We call two chunks duplicates when they share about 75% of their content. To find the similarity this corresponds to, we build one synthetic near-duplicate per chunk by splitting it into sentences and keeping 75% of them at random, in their original order. Each removed sentence is replaced by a random sentence from a chunk of a different article, inserted at a random position. When 75% is not a whole number of sentences we round at random, so the shared fraction is exactly 75% on average. Each fake is scored against its original, and δ is the 5th percentile of the 136 scores, averaged over five random seeds."),
  p("This gives δ = 0.856, with per-seed values from 0.849 to 0.861, and at this level 18 of the 9,180 chunk pairs in the corpus count as duplicates. Sentences are replaced because a copy with sentences only deleted is a subset of its original and scores far higher, with a 5th percentile near 0.92, while real redundant chunks restate shared facts and each add some text of their own. In an early single-seed check, 70% sharing gave δ = 0.823 and flagged 73 pairs, while 80% gave 0.891 and flagged only 4, which suggests repair would rarely act at that level."),

  h2("3.5 Choosing τ"),
  p("The gate should trip when the top-k is at least as redundant as a set that holds one duplicate pair at δ and has every other pair at a typical level b. Setting τ to the signal of that set gives"),
  eq("τ = ( δ + (C(k, 2) − 1) · b ) / C(k, 2)", 2),
  p("We measure b with pseudo-queries. Each of the 136 chunks acts as a query whose top-k is taken from the other 135 chunks, and b is the median of all pair similarities at or below δ across these sets. At k = 3 this gives b = 0.782 and τ = 0.806, and at k = 5 it gives τ = 0.780. τ is recomputed from δ and k at the start of every run. The formula adapts to k, since more pairs dilute the mean, and it places τ just above what a normal top-k looks like on the corpus. Since no evaluation query is used to set δ or τ, the trigger rate is a measured outcome."),
];

const setup = [
  h1("4. Experimental Setup"),
  h2("4.1 Corpus"),
  p("We use three English Wikipedia articles, Diabetes, Type 1 diabetes and Type 2 diabetes, which overlap heavily on symptoms, causes, diagnosis and management, so redundancy across documents occurs naturally. The articles were fetched once and frozen, and their reference, link and see-also sections were removed. The text was split into fixed windows of 150 words with no overlap, dropping trailing windows under 30 words. Overlap was avoided because overlapping windows would create near-duplicates by construction and bias a study of redundancy. The result is 136 chunks from 20,304 words."),
  h2("4.2 Embedding, Retrieval and Hardware"),
  p("Chunks and queries are embedded with BAAI/bge-base-en-v1.5 through the sentence-transformers library, with the BGE retrieval instruction prefix added to queries only. Retrieval is exact cosine search in NumPy, which is enough for 136 chunks. All experiments ran on a laptop with an Intel Core i5-10300H processor (4 cores, 8 threads, up to 4.5 GHz) and 16 GB of RAM, using the CPU build of PyTorch so that similarities are identical across machines."),
  p("To relate comparison counts to real compute, we timed each stage over all 100 queries. The median time to embed one query was about 45 ms. Over the best of five timed passes, retrieving the pool took about 50 µs per query, and selecting the final set took about 18 µs with MMR and 8 µs with the gate at k = 3, rising to about 1.96 ms and 75 µs at k = 15. At k = 3 the gate's share of MMR's time, about 45%, is well above its 11% share of comparisons, because fixed interpreter overhead dominates such small workloads, and both are negligible next to query embedding."),
  h2("4.3 Queries"),
  p("The evaluation set holds 100 queries generated with Claude Opus 5.5 from the corpus text and checked manually by the authors. Fifty are narrow, each targeting one fact in a chunk drawn at random with a fixed seed, for example “Can type 1 diabetes be idiopathic, or is it always caused by an autoimmune attack?”. The other fifty are broad questions on topics covered by at least two articles, such as “What are the symptoms of diabetes?”. We report both groups separately, because the mix of query types could otherwise shape the trigger rate."),
  h2("4.4 Methods Compared"),
  p("All three methods return exactly k chunks from the same pool of 5k candidates. **Plain top-k** returns the k most relevant chunks. **MMR** [1] with λ = 0.7 selects k chunks greedily from the pool. **Gate** is the method of Section 3, with δ = 0.856 and τ derived for each k."),
  h2("4.5 Metrics"),
  p("Trigger rate is the share of queries on which the gate trips. Compute cost is the average number of comparisons per query over all queries, counted in code, which for the gate is C(k,2) plus any repair comparisons. For MMR, round r scores p − r + 1 candidates against r − 1 chosen chunks, so with p = 15 and k = 3 it totals 14 + 26 = 40. Computing τ happens once per run and is excluded."),
  p("Intra-list similarity (ILS) is the mean pairwise similarity of the final set, where lower ILS means less redundancy, and relevance is the mean query-to-chunk similarity of the final set. Because ILS alone can be lowered by returning unrelated chunks, the two are always read together. Every metric is reported for all queries and separately for tripped and untripped ones."),
];

const results = [
  h1("5. Results"),
  h2("5.1 Trigger Rate and Cost"),
  p("The gate tripped on 24 of 100 queries at k = 3 (Figure 1) and used 4.26 comparisons per query on average, about 11% of MMR's 40, while plain top-k uses none. This average combines 3 comparisons on each of the 76 untripped queries with 8.25 on the 24 tripped ones. Broad and narrow queries tripped at similar rates, 26% and 22%, which suggests the query mix did not drive the result."),
  figure("3_where_queries_fall.png", 0.65),
  caption("Figure 1.", "Gate signal of the plain top-3 for each query. Queries to the right of τ = 0.806 were repaired. The rest were returned unchanged after three comparisons."),

  h2("5.2 Redundancy and Relevance"),
  p("Table 1 and Figure 2 give ILS and relevance. On tripped queries the gate lowered ILS from 0.825 to 0.795 while relevance fell by 0.005, and MMR lowered ILS further, to 0.774, with a relevance drop of 0.007. In our setting the gate therefore achieved about 60% of MMR's reduction in redundancy on these queries at about 21% of its cost, 8.25 comparisons against 40."),
  p("On untripped queries the gate returned the plain top-k exactly, whereas MMR still changed 47 of these 76 sets, lowering ILS from 0.773 to 0.745 and relevance from 0.709 to 0.705 at 40 comparisons each. This reduction is modest and occurs on queries the gate classified as not requiring diversification."),
  p("Not every tripped query changed. In 9 of the 24 the mean exceeded τ while no single pair exceeded δ, so dedup found nothing to drop, and these queries spent 6 comparisons before returning the plain top-k."),
  caption("Table 1.", "Mean ILS (lower is less redundant) and relevance at k = 3. The last column is the share of queries whose final set differs from plain top-k."),
  table(
    ["Queries", "Method", "ILS", "Relevance", "Changed"],
    [
      ["All (100)", "Plain top-k", "0.786", "0.714", "0%"],
      ["", "MMR", "0.752", "0.709", "65%"],
      ["", "Gate", "0.778", "0.713", "15%"],
      ["Tripped (24)", "Plain top-k", "0.825", "0.729", "0%"],
      ["", "MMR", "0.774", "0.722", "75%"],
      ["", "Gate", "0.795", "0.724", "63%"],
      ["Not tripped (76)", "Plain top-k", "0.773", "0.709", "0%"],
      ["", "MMR", "0.745", "0.705", "62%"],
      ["", "Gate", "0.773", "0.709", "0%"],
    ],
    [2200, 1800, 1300, 1300, 1300],
  ),
  figure("4_tripped_vs_not_tripped.png", 0.9),
  caption("Figure 2.", "Mean ILS and relevance by method, split by whether the gate tripped. The axes are zoomed because the differences lie in the second and third decimal."),

  h2("5.3 Effect of k"),
  p("Table 2 and Figure 3 repeat the cost measurement for k = 5, 10 and 15, with τ recomputed for each k. Because the pool grows with k as well, MMR's cost grows roughly with the cube of k, rising from 40 to 6,860 comparisons, while the gate's share of that cost falls from 11% to 3%. Wall-clock time follows the same trend at k = 15, where the gate took about 4% of MMR's selection time (Section 4.2). The trigger rate rose from 24% at k = 3 to 46% at k = 5 and stayed near 44% after that, since the formula fixes what a trip means at each k and leaves the share of queries that trip free to vary. The fallback for an exhausted reserve was never triggered at any k."),
  caption("Table 2.", "Average comparisons per query as k grows. τ is derived for each k from δ = 0.856."),
  table(
    ["k", "τ", "MMR", "Gate", "Gate / MMR", "Trigger rate"],
    [
      ["3", "0.806", "40", "4.26", "11%", "24%"],
      ["5", "0.780", "220", "18.41", "8%", "46%"],
      ["10", "0.760", "1,965", "91.42", "5%", "44%"],
      ["15", "0.749", "6,860", "224.58", "3%", "43%"],
    ],
    [900, 1200, 1400, 1400, 1500, 1600],
  ),
  figure("2_cost_vs_k.png", 0.8),
  caption("Figure 3.", "Average comparisons per query as k grows. Plain top-k costs zero at every k."),
];

const discussion = [
  h1("6. Discussion and Limitations"),
  p("Within the limits of one corpus, the results suggest that most queries did not need diversification and that the gate let them skip it for C(k,2) lookups. Where the gate acted, it recovered a large part of MMR's reduction in redundancy for a fraction of the comparisons. Over all 100 queries it achieved about 22% of MMR's reduction in ILS, so MMR remains the better choice when the lowest possible redundancy matters more than compute."),
  p("The gate and the repair apply different tests, since the gate looks at the mean over all pairs while dedup looks at single pairs, and the two can disagree in both directions. A set of uniformly similar chunks can trip the gate without holding a duplicate, as happened on 9 queries, and a set with one duplicate pair and two dissimilar pairs can pass the gate and keep its duplicate. We accept this mismatch for two reasons. A set whose pairs are all moderately similar usually covers one topic from several angles, and a single duplicate pair in an otherwise diverse set costs only one slot out of k. Removing the mismatch would also mean either tripping the gate more often or lowering δ, which on this corpus would flag more adjacent passages as duplicates. Whether repeated evidence helps or hurts the generated answer was not measured, so this remains an assumption of the design."),
  p("A single similarity score cannot fully separate a continuation from a copy. Adjacent chunks in one article share no sentences, yet 7 of the 133 adjacent pairs score above δ, reaching 0.896, which indicates that BGE rates the next paragraph on the same subject about as high as a 75% copy, a blind spot MMR shares because it depends on the same scores."),
  p("The study is small, with one corpus of 136 chunks, one embedding model and 100 queries generated by a language model, so the findings may not carry over to larger or more varied collections. Differences in ILS and relevance are small in absolute terms because BGE similarities fall in a narrow band. Our timings indicate that at k = 3 the saving is about 10 µs per query, far below the roughly 45 ms spent embedding the query. The saving grows with k and pool size, reaching about 1.9 ms per query at k = 15, and it would matter more in systems that compute similarities on demand. We did not measure the effect on generated answers."),
];

const conclusion = [
  h1("7. Conclusion"),
  p("Where MMR spends the same effort on every query, a cheap redundancy gate can limit that effort to the queries that appear to need it. On a corpus chosen for its overlapping content, 76% of queries passed the gate and were returned unchanged after three comparisons. The gate method used about 11% of MMR's comparisons at k = 3 and about 3% at k = 15 while keeping relevance close to plain retrieval, with both thresholds derived from the corpus by a fixed rule. Future work could test larger and more varied corpora, other embedding models, and the effect on answer quality."),
];

const references = [
  h1("References"),
  // Taken from the Project I report (paper/BCSE497J Project I Report ... .pdf), same
  // order and numbering. Page ranges use a hyphen.
  ref("[1] J. Carbonell and J. Goldstein. The Use of MMR, Diversity-Based Reranking for Reordering Documents and Producing Summaries. In *Proceedings of the 21st Annual International ACM SIGIR Conference on Research and Development in Information Retrieval (SIGIR '98)*, pages 335-336. ACM, 1998."),
  ref("[2] M. R. Vieira, H. L. Razente, M. C. N. Barioni, M. Hadjieleftheriou, D. Srivastava, A. Traina and V. J. Tsotras. On Query Result Diversification. In *2011 IEEE 27th International Conference on Data Engineering (ICDE)*, pages 1163-1174. IEEE, 2011."),
  ref("[3] M. Drosou and E. Pitoura. Search Result Diversification. *ACM SIGMOD Record*, 39(1), pages 41-47, 2010."),
  ref("[4] M. Drosou and E. Pitoura. Diverse Set Selection Over Dynamic Data. *IEEE Transactions on Knowledge and Data Engineering*, 26(5), pages 1102-1116, 2014."),
  ref("[5] K. Zheng, H. Wang, Z. Qi, J. Li and H. Gao. A Survey of Query Result Diversification. *Knowledge and Information Systems*, 51(1), pages 1-36, 2017."),
  ref("[6] Y. Huang and J. X. Huang. A Survey on Retrieval-Augmented Text Generation for Large Language Models. *ACM Computing Surveys*, 58(12), Article 300, May 2026."),
  ref("[7] F. Cuconasu, G. Trappolini, F. Siciliano, S. Filice, C. Campagnano, Y. Maarek, N. Tonellotto and F. Silvestri. The Power of Noise: Redefining Retrieval for RAG Systems. In *Proceedings of the 47th International ACM SIGIR Conference on Research and Development in Information Retrieval (SIGIR '24)*, pages 719-729. ACM, 2024."),
  ref("[8] A. Salemi and H. Zamani. Evaluating Retrieval Quality in Retrieval-Augmented Generation. In *Proceedings of the 47th International ACM SIGIR Conference on Research and Development in Information Retrieval (SIGIR '24)*, pages 2395-2400. ACM, 2024."),
  ref("[9] W. Fan, Y. Ding, L. Ning, S. Wang, H. Li, D. Yin, T. S. Chua and Q. Li. A Survey on RAG Meeting LLMs: Towards Retrieval-Augmented Large Language Models. In *Proceedings of the 30th ACM SIGKDD Conference on Knowledge Discovery and Data Mining (KDD '24)*, pages 6491-6501. ACM, 2024."),
  ref("[10] L. Huang, W. Yu, W. Ma, W. Zhong, Z. Feng, H. Wang, Q. Chen, W. Peng, X. Feng, B. Qin and T. Liu. A Survey on Hallucination in Large Language Models: Principles, Taxonomy, Challenges, and Open Questions. *ACM Transactions on Information Systems*, 43(2), pages 1-55, January 2025."),
  ref("[11] S. Agarwal, S. N. Sundaresan, S. Mitra, D. Mahapatra, T. Yu and S. Saini. Cache-Craft: Managing Chunk-Caches for Efficient Retrieval-Augmented Generation. In *Proceedings of the 2025 ACM SIGMOD International Conference on Management of Data (SIGMOD '25)*. ACM, 2025."),
];

// ---------- document ----------

const numbered = (reference) => ({
  reference,
  levels: [{
    level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 567, hanging: 340 } } },
  }],
});

const doc = new Document({
  creator: "Nishant Ajit, Jeevaanandh Vi, Pratyush Kumar V",
  title: "Redundancy-Gated Retrieval: Optimized Diversification of RAG Context",
  styles: { default: { document: { run: { font: FONT, size: BODY } } } },
  numbering: { config: [numbered("contrib"), numbered("steps")] },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_W, height: PAGE_H },
        margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN },
      },
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ children: [PageNumber.CURRENT], size: 20 })],
        })],
      }),
    },
    children: [
      ...title, ...abstract, ...intro, ...related, ...method, ...setup, ...results,
      ...discussion, ...conclusion, ...references,
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = path.join(__dirname, "paper.docx");
  fs.writeFileSync(out, buf);
  console.log(`wrote ${out}`);
});
