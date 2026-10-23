"""Run all three methods over the query set and collect one row per query and method.

This is the evaluation harness (stage 7). It reuses exactly the functions main.py uses for
a single query, so the numbers in results/ are the same ones you would see by running
main.py on any one of the queries. See docs/EVALUATION.md.
"""

import json
from pathlib import Path

import numpy as np

from src.calibrate import compute_tau
from src.embed import embed_query
from src.gate import run_gate
from evaluation.metrics import ils, mean_relevance
from src.mmr import mmr
from src.repair import repair
from src.retrieve import plain_top_k, reserve, retrieve_pool

METHODS = ["plain", "mmr", "gate"]


def load_queries(path: str | Path) -> list[dict]:
    """The query list from data/queries.json. Each has id, type, and text."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["queries"]


def embed_queries(queries: list[dict], model_name: str, device: str) -> np.ndarray:
    """Embed every query once, with the BGE prefix. Shape (n_queries, 768)."""
    return np.array([embed_query(q["text"], model_name, device) for q in queries])


def run_one_query(
    query_emb: np.ndarray,
    embeddings: np.ndarray,
    sim_matrix: np.ndarray,
    config: dict,
    k: int,
    tau: float,
) -> dict[str, dict]:
    """Plain, MMR and gate for one query. Returns {method: result}.

    Each result has the final chunk ids and the comparisons the method spent. The gate
    result also says whether the gate tripped and what its signal was.
    """
    repair_cfg = config["repair"]
    pool = retrieve_pool(query_emb, embeddings, k * config["retrieval"]["pool_multiplier"])
    relevance = {chunk_id: score for chunk_id, score in pool}

    plain = plain_top_k(pool, k)
    mmr_ids, mmr_cost = mmr(pool, sim_matrix, k, config["mmr"]["lambda"])

    gate = run_gate(plain, sim_matrix, tau)
    gate_ids, gate_cost, relaxed = plain, gate.comparisons, 0
    if gate.trips:
        result = repair(
            plain,
            reserve(pool, k),
            sim_matrix,
            relevance,
            repair_cfg["delta"],
            k,
            repair_cfg["backfill_check"],
            repair_cfg["exhaustion_fallback"],
        )
        gate_ids = result.final_ids
        gate_cost = gate.comparisons + result.comparisons
        relaxed = len(result.relaxed)

    results = {
        "plain": {"ids": plain, "comparisons": 0},
        "mmr": {"ids": mmr_ids, "comparisons": mmr_cost},
        "gate": {"ids": gate_ids, "comparisons": gate_cost, "relaxed": relaxed},
    }
    for res in results.values():
        res["ils"] = ils(res["ids"], sim_matrix)
        res["relevance"] = mean_relevance(res["ids"], relevance)
        res["changed"] = set(res["ids"]) != set(plain)
        res["tripped"] = gate.trips
        res["signal"] = gate.signal
    return results


def run_experiment(
    queries: list[dict],
    query_embs: np.ndarray,
    embeddings: np.ndarray,
    sim_matrix: np.ndarray,
    config: dict,
    k: int,
) -> list[dict]:
    """Every query through every method at one k. One flat row per query and method,
    ready to write to CSV. tau is worked out for this k on the fly (METHOD.md section 4),
    so graph 2 gets a matching tau at every k."""
    tau = compute_tau(sim_matrix, k, config["repair"]["delta"])
    rows = []
    for query, query_emb in zip(queries, query_embs):
        results = run_one_query(query_emb, embeddings, sim_matrix, config, k, tau)
        for method in METHODS:
            res = results[method]
            rows.append({
                "query_id": query["id"],
                "query_type": query["type"],
                "k": k,
                "tau": round(tau, 4),
                "method": method,
                "tripped": res["tripped"],
                "signal": round(res["signal"], 4),
                "comparisons": res["comparisons"],
                "ils": round(res["ils"], 4),
                "relevance": round(res["relevance"], 4),
                "changed_vs_plain": res["changed"],
                "relaxed": res.get("relaxed", ""),
                "chunk_ids": " ".join(str(i) for i in res["ids"]),
            })
    return rows
