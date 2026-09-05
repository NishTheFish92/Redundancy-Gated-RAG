"""Run one query through all three methods and print what each returns.

    uv run python main.py "what causes type 2 diabetes"
    uv run python main.py "insulin treatment" --k 5

Three methods, same query, same pool:

  plain   the k most relevant chunks, no diversification. What standard RAG returns.
  mmr     the established baseline. Diversifies on every query, always pays the cost.
  gate    this project. Checks cheaply whether the top-k is redundant, and only repairs
          it if it is. On the queries that are already diverse it returns the plain
          top-k having spent just C(k,2) comparisons.

The number to watch is `comparisons`, the count of similarity lookups each method spent.
That is the contribution: on a non-redundant query the gate should cost far less than MMR
while returning the same thing.
"""

import argparse
import sys

from src.config import load_config, resolve_path
from src.corpus import chunk_pages, load_pages
from src.embed import build_or_load_embeddings, embed_query, similarity_matrix
from src.gate import run_gate
from src.mmr import mmr
from src.repair import repair
from src.retrieve import plain_top_k, reserve, retrieve_pool


def build_index(config):
    """Load the corpus, embed it, and build the similarity matrix. Cached after run 1."""
    corpus_cfg, model_cfg = config["corpus"], config["model"]

    pages = load_pages(
        resolve_path(corpus_cfg["raw_dir"]),
        corpus_cfg["pages"],
        corpus_cfg["strip_sections"],
        corpus_cfg["keep_headings"],
    )
    chunks = chunk_pages(
        pages,
        corpus_cfg["chunk_size_words"],
        corpus_cfg["overlap_words"],
        corpus_cfg["min_chunk_words"],
    )
    embeddings = build_or_load_embeddings(
        [chunk.text for chunk in chunks],
        model_cfg["name"],
        resolve_path(model_cfg["cache_path"]),
        model_cfg["normalize"],
        model_cfg["batch_size"],
        model_cfg["device"],
        verbose=False,
    )
    return chunks, embeddings, similarity_matrix(embeddings)


def show(title, chunk_ids, chunks, relevance, comparisons, note=""):
    """Print one method's result."""
    print(f"\n{title}")
    print(f"  comparisons spent: {comparisons}{note}")
    for chunk_id in chunk_ids:
        text = " ".join(chunks[chunk_id].text.split())[:110]
        print(f"    c{chunk_id:<4} rel {relevance[chunk_id]:.3f}  "
              f"[{chunks[chunk_id].page}]")
        print(f"           {text}...")


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the three retrieval methods.")
    parser.add_argument("query", help="the search query, in quotes")
    parser.add_argument("--k", type=int, default=None, help="override k from config")
    parser.add_argument("--tau", type=float, default=None, help="override tau from config")
    args = parser.parse_args()

    config = load_config()
    model_cfg = config["model"]
    k = args.k if args.k is not None else config["retrieval"]["k"]
    tau = args.tau if args.tau is not None else config["gate"]["tau"]
    delta = config["repair"]["delta"]
    pool_size = k * config["retrieval"]["pool_multiplier"]

    if args.k is not None and args.k != config["retrieval"]["k"]:
        print(
            f"WARNING: k overridden to {args.k}, but tau={tau} was calibrated for "
            f"k={config['retrieval']['k']}. Gate signals shrink as k grows, so the "
            f"trigger rate here is not meaningful. See config.yaml.\n",
            file=sys.stderr,
        )

    chunks, embeddings, sim_matrix = build_index(config)

    prefix = model_cfg["query_prefix_text"] if model_cfg["query_prefix"] else None
    query_emb = embed_query(
        args.query, model_cfg["name"], prefix, model_cfg["normalize"], model_cfg["device"]
    )

    pool = retrieve_pool(query_emb, embeddings, pool_size)
    relevance = {chunk_id: score for chunk_id, score in pool}

    print("=" * 78)
    print(f"query : {args.query}")
    print(f"corpus: {len(chunks)} chunks | k={k}  pool={pool_size}  "
          f"tau={tau}  delta={delta}")
    print("=" * 78)

    # 1. Plain top-k. No chunk-to-chunk work at all.
    plain = plain_top_k(pool, k)
    show("PLAIN TOP-K (what standard RAG returns)", plain, chunks, relevance, 0)

    # 2. MMR. Diversifies every query whether it needs it or not.
    mmr_ids, mmr_cost = mmr(pool, sim_matrix, k, config["mmr"]["lambda"])
    show("MMR BASELINE (always-on diversification)", mmr_ids, chunks, relevance, mmr_cost)

    # 3. The gate method. Cheap check first, repair only if it trips.
    gate_result = run_gate(plain, sim_matrix, tau, config["gate"]["averaging"])
    print(f"\nGATE CHECK")
    print(f"  signal {gate_result.signal:.4f} vs tau {tau}  ->  "
          f"{'TRIPPED, repairing' if gate_result.trips else 'clean, shipping plain top-k'}")
    for i, j, sim in gate_result.pairs:
        print(f"    c{i} <-> c{j}: {sim:.3f}{'   above delta' if sim > delta else ''}")

    if gate_result.trips:
        repair_cfg = config["repair"]
        result = repair(
            plain,
            reserve(pool, k),
            sim_matrix,
            relevance,
            delta,
            k,
            repair_cfg["multiway_rule"],
            repair_cfg["backfill_check"],
            repair_cfg["exhaustion_fallback"],
        )
        gate_ids = result.final_ids
        gate_cost = gate_result.comparisons + result.comparisons
        note = f"  ({gate_result.comparisons} gate + {result.comparisons} repair)"
        detail = (f"  dropped {result.dropped}  added {result.added}"
                  f"{'  relaxed ' + str(result.relaxed) if result.relaxed else ''}")
    else:
        gate_ids = plain
        gate_cost = gate_result.comparisons
        note = "  (gate only, repair skipped)"
        detail = "  identical to plain top-k"

    show("GATE METHOD (this project)", gate_ids, chunks, relevance, gate_cost, note)
    print(f"  {detail}")

    print("\n" + "-" * 78)
    print(f"cost: plain 0  |  mmr {mmr_cost}  |  gate {gate_cost}", end="")
    if mmr_cost:
        print(f"   ->  gate spent {100 * gate_cost / mmr_cost:.0f}% of what MMR spent")
    else:
        print()
    print(f"agreement: gate vs mmr {'SAME set' if set(gate_ids) == set(mmr_ids) else 'different sets'}"
          f"  |  gate vs plain {'SAME set' if set(gate_ids) == set(plain) else 'different sets'}")


if __name__ == "__main__":
    main()
