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
  const cell = (text, i, { bold = false, top = NONE, bottom = NONE } = {}) => new TableCell({
    width: { size: colWidths[i], type: WidthType.DXA },
    borders: { top, bottom, left: NONE, right: NONE },
    margins: { top: 40, bottom: 40, left: 100, right: 100 },
    children: [new Paragraph({
      keepNext: true,
      alignment: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER,
      children: [new TextRun({ text, bold, size: 20 })],
    })],
  });
  const head = new TableRow({
    tableHeader: true,
    children: header.map((t, i) => cell(t, i, { bold: true, top: LINE, bottom: LINE })),
  });
  const body = rows.map((r, ri) => new TableRow({
    children: r.map((t, i) => cell(t, i, { bottom: ri === rows.length - 1 ? LINE : NONE })),
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
      ...runs("Retrieval-augmented generation (RAG) passes the k chunks most similar to a query to a language model. These chunks are often near-duplicates of each other, so part of the context window repeats the same evidence. Maximal Marginal Relevance (MMR) reduces this redundancy by re-ranking a candidate pool, but it does so on every query, including queries whose top-k is already diverse. We propose a redundancy gate that computes the mean pairwise similarity of the plain top-k and runs a repair step only when that mean exceeds a threshold. The repair drops near-duplicate chunks and backfills the freed slots from a larger pool. Both thresholds are derived from the corpus by a fixed rule, without using the evaluation queries. On 100 queries over three overlapping Wikipedia articles on diabetes, the gate tripped on 24% of queries at k = 3. It used 4.26 similarity comparisons per query on average, against 40 for always-on MMR. On tripped queries it lowered intra-list similarity from 0.825 to 0.795 while mean relevance moved from 0.729 to 0.724. MMR reduced redundancy further, to 0.774, at a higher cost. The cost gap widens with k. At k = 15 the gate used about 3% of MMR's comparisons."),
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
  p("Retrieval-augmented generation grounds a language model in text retrieved at query time [1]. A typical pipeline embeds the query, ranks corpus chunks by similarity to it, and keeps the top k. Similarity to the query says nothing about similarity among the chunks themselves. When several sources describe the same fact, the top-k can hold two or three restatements of it. Those extra slots carry no new evidence."),
  p("MMR [2] is the standard remedy. It builds the result one chunk at a time and penalizes candidates that resemble chunks already chosen. Later diversification methods follow the same pattern, and they all re-rank on every query. Many queries, however, return a top-k that is already diverse. For those, the re-ranking spends compute and may swap a relevant chunk for a less relevant one."),
  p("This paper makes diversification conditional. A cheap check, the gate, reads the C(k,2) pairwise similarities inside the plain top-k. At k = 3 that is three lookups. If their mean is at or below a threshold τ, the top-k is returned unchanged. Otherwise a repair step removes pairs above a duplicate threshold δ and refills the freed slots from a larger candidate pool. The contributions are as follows."),
  item("A redundancy gate and a threshold-based repair step that diversify only the queries that need it.", "contrib"),
  item("A rule that sets both thresholds from the corpus. δ comes from synthetic near-duplicates, and τ is derived from δ and k.", "contrib"),
  item("An evaluation that counts similarity comparisons in code and reports every metric separately for queries where the gate tripped and where it did not.", "contrib"),
  p("The claim of this work is efficiency. On diversity alone MMR remains stronger, and Section 5 reports by how much."),
];

const related = [
  h1("2. Related Work"),
  p("Carbonell and Goldstein introduced MMR for document re-ranking and summarization [2]. At each step it selects the candidate that maximizes a weighted difference between relevance to the query and the highest similarity to anything already selected. A weight λ sets the balance. MMR remains the usual way to diversify retrieved context, and common RAG toolkits offer it as a retrieval option."),
  p("Intra-list similarity (ILS) comes from work on recommender systems, where it measures how alike the items in one list are [3]. We use it as the measure of redundancy in a retrieved set. Our retriever uses dense sentence embeddings [4] from the BGE family [5]."),
  p("Adaptive retrieval methods make parts of the RAG pipeline conditional. Self-RAG trains the model to decide when to retrieve and to critique its own output [6]. Adaptive-RAG routes each query to a retrieval strategy based on its predicted complexity [7]. Both decide from the query or the model. The gate in this paper decides from the retrieved set and needs no training."),
  p("Evaluation frameworks for RAG such as RAGAS focus on faithfulness and answer relevance [8]. They do not measure redundancy among retrieved chunks, so we use a small harness that counts comparisons and computes ILS directly."),
];

const method = [
  h1("3. Method"),
  h2("3.1 Overview"),
  p("Every embedding is L2-normalized, so cosine similarity equals the dot product. The chunk-to-chunk similarity matrix S = EEᵀ is computed once and cached. After that, every chunk-to-chunk similarity is a single lookup in S. We count one lookup as one comparison, and all costs in this paper are given in comparisons. For a query q the pipeline runs four steps."),
  item("Retrieve a pool of the p = 5k chunks most similar to q. Ties in relevance are broken by chunk id.", "steps"),
  item("Split the pool into the plain top-k T and a reserve R that holds the remaining chunks in relevance order.", "steps"),
  item("Compute the gate signal on T. If it does not exceed τ, return T.", "steps"),
  item("Otherwise repair T using R and return the result.", "steps"),

  h2("3.2 The Gate"),
  p("The gate signal is the mean pairwise similarity inside the plain top-k."),
  eq("g(T) = Σ S(i, j) / C(k, 2),   over all pairs i < j in T", 1),
  p("The gate trips when g(T) > τ. It costs C(k,2) comparisons on every query, which is 3 at k = 3 and 10 at k = 5. We also tried weighting each pair by the relevance of its members. Relevance values inside a BGE top-k are nearly equal, for example 0.78, 0.76 and 0.75. The weighted signal therefore barely differed from the plain mean, and we kept the plain mean."),

  h2("3.3 The Repair"),
  p("Repair has two stages. Dedup removes near-duplicates from T, and backfill refills the freed slots from R."),
  p("Dedup finds the most similar pair in the current set with S(i, j) > δ and drops the member with lower relevance. It then rechecks the smaller set and repeats until no pair exceeds δ. Dropping one chunk at a time matters when three or more chunks are similar. Suppose A-B scores 0.95, B-C scores 0.90 and A-C scores 0.70, with δ anywhere between 0.70 and 0.90. Removing the weaker member of every flagged pair in one pass leaves only A. The iterative rule drops B, finds A-C below δ, and keeps both."),
  p("Backfill walks R in relevance order. A candidate is accepted if its similarity to every chunk already kept is at most δ. If not, it is rejected and the walk moves on. Each accepted chunk joins the kept set, so later candidates are checked against it too. The walk stops once the set is back to k chunks. If R runs out first, a fallback re-admits the rejected candidate least similar to the kept set until there are k chunks. This keeps the output size equal across methods so their metrics compare fairly. The fallback was never needed in our experiments."),
  p("Repair is cheaper than MMR because of what it checks. MMR rescores every remaining candidate against every selected chunk in each round. Repair checks only the candidates it walks past, and only against the chunks it keeps. The price is that repair uses fixed thresholds with no continuous trade-off, so its output can stay more redundant than MMR's."),

  h2("3.4 Choosing δ"),
  p("Thresholds picked by intuition do not transfer to BGE. On our corpus unrelated text often scores between 0.6 and 0.7, and a typical pair inside a top-3 scores about 0.78. Both thresholds are therefore derived from the corpus by a fixed rule."),
  p("We call two chunks duplicates when they share about 75% of their content. To find the similarity this corresponds to, we build one synthetic near-duplicate per chunk. The chunk is split into sentences and 75% of them are kept at random, in their original order. Each removed sentence is replaced by a random sentence from a chunk of a different article, inserted at a random position. When 75% is not a whole number of sentences we round at random, so the shared fraction is exactly 75% on average. Each fake is scored against its original. δ is the 5th percentile of the 136 scores, averaged over five random seeds."),
  p("This gives δ = 0.856, with per-seed values from 0.849 to 0.861. At this level 18 of the 9,180 chunk pairs in the corpus count as duplicates. Replacing sentences matters. A copy with sentences only deleted is a subset of its original and scores far higher, with a 5th percentile near 0.92. Real redundant chunks restate shared facts and each add some text of their own. In an early single-seed check, 70% sharing gave δ = 0.823 and flagged 73 pairs. 80% gave 0.891 and flagged only 4, too few for repair to ever act."),

  h2("3.5 Choosing τ"),
  p("The gate should trip when the top-k is at least as redundant as a set that holds one duplicate pair at δ and has every other pair at a typical level b. Setting τ to the signal of that set gives"),
  eq("τ = ( δ + (C(k, 2) − 1) · b ) / C(k, 2)", 2),
  p("We measure b with pseudo-queries. Each of the 136 chunks acts as a query, and its top-k is taken from the other 135 chunks. b is the median of all pair similarities at or below δ across these sets. At k = 3 this gives b = 0.782 and τ = 0.806. At k = 5 it gives τ = 0.780. τ is recomputed from δ and k at the start of every run. The formula adapts to k, since more pairs dilute the mean, and it places τ just above what a normal top-k looks like on the corpus. No evaluation query is used to set δ or τ, so the trigger rate is a measured outcome."),
];

const setup = [
  h1("4. Experimental Setup"),
  h2("4.1 Corpus"),
  p("We use three English Wikipedia articles, Diabetes, Type 1 diabetes and Type 2 diabetes. They overlap heavily on symptoms, causes, diagnosis and management, so redundancy across documents occurs naturally. The articles were fetched once and frozen. Reference, link and see-also sections were removed. The text was split into fixed windows of 150 words with no overlap, and trailing windows under 30 words were dropped. Overlapping windows would create near-duplicates by construction and bias a study of redundancy. The result is 136 chunks from 20,304 words."),
  h2("4.2 Embedding and Retrieval"),
  p("Chunks and queries are embedded with BAAI/bge-base-en-v1.5 [5] through the sentence-transformers library [4]. Queries carry the BGE retrieval instruction prefix. Chunks do not. All runs use the CPU so that similarities are identical across machines. Retrieval is exact cosine search in NumPy, which is enough for 136 chunks."),
  h2("4.3 Queries"),
  p("The evaluation set holds 100 queries generated with a large language model from the corpus text. Fifty are narrow. Each targets one fact in a chunk drawn at random with a fixed seed, for example “Can type 1 diabetes be idiopathic, or is it always caused by an autoimmune attack?”. The other fifty are broad questions on topics covered by at least two articles, such as “What are the symptoms of diabetes?”. We report both groups separately, because the mix of query types could otherwise shape the trigger rate."),
  h2("4.4 Methods Compared"),
  p("All three methods return exactly k chunks from the same pool of 5k candidates. **Plain top-k** returns the k most relevant chunks. **MMR** [2] with λ = 0.7 selects k chunks greedily from the pool. **Gate** is the method of Section 3, with δ = 0.856 and τ derived for each k."),
  h2("4.5 Metrics"),
  p("Trigger rate is the share of queries on which the gate trips. Compute cost is the average number of comparisons per query over all queries, counted in code. For the gate this is C(k,2) plus any repair comparisons. For MMR, round r scores p − r + 1 candidates against r − 1 chosen chunks. With p = 15 and k = 3 this totals 14 + 26 = 40. Computing τ happens once per run and is excluded."),
  p("ILS is the mean pairwise similarity of the final set [3]. Lower ILS means less redundancy. Relevance is the mean query-to-chunk similarity of the final set. ILS alone can be lowered by returning unrelated chunks, so the two are always read together. Every metric is reported for all queries and separately for tripped and untripped ones."),
];

const results = [
  h1("5. Results"),
  h2("5.1 Trigger Rate and Cost"),
  p("The gate tripped on 24 of 100 queries at k = 3 (Figure 1). It used 4.26 comparisons per query on average, about 11% of MMR's 40. Plain top-k uses none. The gate's average combines 3 comparisons on each of the 76 untripped queries with 8.25 on the 24 tripped ones. Broad and narrow queries tripped at similar rates, 26% and 22%."),
  figure("3_where_queries_fall.png", 0.65),
  caption("Figure 1.", "Gate signal of the plain top-3 for each query. Queries to the right of τ = 0.806 were repaired. The rest were returned unchanged after three comparisons."),

  h2("5.2 Redundancy and Relevance"),
  p("Table 1 and Figure 2 give ILS and relevance. On tripped queries the gate lowered ILS from 0.825 to 0.795, and relevance fell by 0.005. MMR lowered ILS further, to 0.774, with a relevance drop of 0.007. The gate thus achieved about 60% of MMR's reduction in redundancy on these queries at about 21% of its cost, 8.25 comparisons against 40."),
  p("On untripped queries the gate returned the plain top-k exactly. MMR still changed 47 of these 76 sets. It lowered ILS from 0.773 to 0.745 and relevance from 0.709 to 0.705, paying 40 comparisons each time. The gain is real and small, and it came on queries the gate judged to need no work."),
  p("Not every tripped query changed. In 9 of the 24 the mean exceeded τ while no single pair exceeded δ, so dedup found nothing to drop. These queries cost 6 comparisons and returned the plain top-k."),
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
  p("Table 2 and Figure 3 repeat the cost measurement for k = 5, 10 and 15, with τ recomputed for each k. MMR's cost grows roughly with the cube of k, since the pool grows with k as well. It rises from 40 to 6,860 comparisons. The gate's share of that cost falls from 11% to 3%. The trigger rate rose from 24% at k = 3 to 46% at k = 5 and stayed near 44% after that. The formula fixes what a trip means at each k, and the share of queries that trip is left free to vary. The fallback for an exhausted reserve was never triggered at any k."),
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
  p("The results support a narrow claim. Most queries in our set did not need diversification, and the gate let them skip it for C(k,2) lookups. Where it acted, it recovered a large part of MMR's reduction in redundancy for a fraction of the comparisons. MMR remains the better choice when the lowest possible redundancy matters more than compute. Over all 100 queries the gate achieved about 22% of MMR's reduction in ILS."),
  p("The gate and the repair apply different tests. The gate looks at the mean over all pairs, and dedup looks at single pairs. The two can disagree in both directions. A set of uniformly similar chunks can trip the gate without holding a duplicate, as happened on 9 queries. A set with one duplicate pair and two dissimilar pairs can pass the gate and keep its duplicate. We accept this, since some repetition can reinforce a fact."),
  p("A single similarity score cannot fully separate a continuation from a copy. Adjacent chunks in one article share no sentences, yet 7 of the 133 adjacent pairs score above δ, reaching 0.896. BGE rates the next paragraph on the same subject about as high as a 75% copy. MMR depends on the same scores and shares this blind spot."),
  p("The study is small. It uses one corpus of 136 chunks, one embedding model and 100 queries written by a language model. Differences in ILS and relevance are small in absolute terms because BGE similarities fall in a narrow band. Comparison counts stand in for compute time. At k = 3 the absolute saving per query is tiny. It grows with k, with pool size, and in systems that compute similarities on demand. We did not measure the effect on generated answers."),
];

const conclusion = [
  h1("7. Conclusion"),
  p("MMR spends the same effort on every query. A cheap redundancy gate can limit that effort to the queries that need it. On a corpus chosen for its overlapping content, 76% of queries passed the gate and were returned unchanged after three comparisons. The gate method used about 11% of MMR's comparisons at k = 3 and about 3% at k = 15, and its relevance stayed close to plain retrieval. Both thresholds come from the corpus by a fixed rule. Future work could test larger and more varied corpora, other embedding models, and the effect on answer quality."),
];

const references = [
  h1("References"),
  ref("[1] P. Lewis, E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Küttler, M. Lewis, W. Yih, T. Rocktäschel, S. Riedel and D. Kiela. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. In *Advances in Neural Information Processing Systems 33*, 2020."),
  ref("[2] J. Carbonell and J. Goldstein. The Use of MMR, Diversity-Based Reranking for Reordering Documents and Producing Summaries. In *Proceedings of the 21st ACM SIGIR Conference on Research and Development in Information Retrieval*, pages 335-336, 1998."),
  ref("[3] C.-N. Ziegler, S. M. McNee, J. A. Konstan and G. Lausen. Improving Recommendation Lists Through Topic Diversification. In *Proceedings of the 14th International Conference on World Wide Web*, pages 22-32, 2005."),
  ref("[4] N. Reimers and I. Gurevych. Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. In *Proceedings of EMNLP-IJCNLP*, 2019."),
  ref("[5] S. Xiao, Z. Liu, P. Zhang and N. Muennighoff. C-Pack: Packaged Resources To Advance General Chinese Embedding. arXiv preprint arXiv:2309.07597, 2023."),
  ref("[6] A. Asai, Z. Wu, Y. Wang, A. Sil and H. Hajishirzi. Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection. In *International Conference on Learning Representations*, 2024."),
  ref("[7] S. Jeong, J. Baek, S. Cho, S. J. Hwang and J. C. Park. Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity. In *Proceedings of NAACL-HLT*, 2024."),
  ref("[8] S. Es, J. James, L. Espinosa-Anke and S. Schockaert. RAGAS: Automated Evaluation of Retrieval Augmented Generation. In *Proceedings of EACL, System Demonstrations*, 2024."),
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
