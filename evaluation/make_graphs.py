"""Run the evaluation and draw the five core graphs into results/.

    uv run python evaluation/make_graphs.py
    uv run python evaluation/make_graphs.py --out some/other/folder

Writes:
  results/per_query.csv     one row per query and method, at the configured k
  results/summary.csv       the comparison table, split by tripped / not tripped and by
                            broad / narrow queries
  results/cost_vs_k.csv     the data behind graph 2
  results/figures/          the five graphs as PNG

The graphs and their messages are fixed in docs/EVALUATION.md, section "Graphs".
"""

import argparse
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # write files only, never open a window
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# Make `src`, `evaluation` and `main` importable when this file is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import build_index  # noqa: E402
from src.config import load_config, resolve_path  # noqa: E402
from evaluation.experiment import (  # noqa: E402
    METHODS,
    embed_queries,
    load_queries,
    run_experiment,
)

# Colours. One fixed colour per method, used in every graph, validated for colour-blind
# readers (dataviz reference palette, slots 1 to 3). Aqua sits below 3:1 contrast on the
# light background, so every graph labels its marks directly as well.
COLOURS = {"plain": "#2a78d6", "mmr": "#eb6834", "gate": "#1baf7a"}
LABELS = {"plain": "Plain top-k", "mmr": "MMR", "gate": "Gate (ours)"}
SHIPPED_GREY = "#898781"
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": TEXT_SECONDARY,
    "axes.titlecolor": TEXT,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "xtick.color": TEXT_SECONDARY,
    "ytick.color": TEXT_SECONDARY,
    "legend.frameon": False,
    "font.size": 10,
})


# ---------- tables ----------

def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def rows_for(rows: list[dict], method: str, subset: str) -> list[dict]:
    """Rows of one method inside one group of queries."""
    keep = {
        "all": lambda r: True,
        "tripped": lambda r: r["tripped"],
        "not_tripped": lambda r: not r["tripped"],
        "broad": lambda r: r["query_type"] == "broad",
        "narrow": lambda r: r["query_type"] == "narrow",
    }[subset]
    return [r for r in rows if r["method"] == method and keep(r)]


def summarise(rows: list[dict]) -> list[dict]:
    """Averages per method, for every group of queries. A group with no queries in it
    (for example nothing tripped) is skipped rather than averaged over nothing."""
    summary = []
    for subset in ["all", "tripped", "not_tripped", "broad", "narrow"]:
        for method in METHODS:
            group = rows_for(rows, method, subset)
            if not group:
                continue
            summary.append({
                "queries": subset,
                "method": method,
                "n_queries": len(group),
                "trip_rate": round(np.mean([r["tripped"] for r in group]), 4),
                "mean_comparisons": round(np.mean([r["comparisons"] for r in group]), 2),
                "mean_ils": round(np.mean([r["ils"] for r in group]), 4),
                "mean_relevance": round(np.mean([r["relevance"] for r in group]), 4),
                "share_changed_vs_plain": round(
                    np.mean([r["changed_vs_plain"] for r in group]), 4
                ),
            })
    return summary


def cost_vs_k(rows_by_k: dict[int, list[dict]]) -> list[dict]:
    out = []
    for k, rows in rows_by_k.items():
        for method in METHODS:
            group = rows_for(rows, method, "all")
            out.append({
                "k": k,
                "tau": group[0]["tau"],
                "method": method,
                "mean_comparisons": round(np.mean([r["comparisons"] for r in group]), 2),
                "trip_rate": round(np.mean([r["tripped"] for r in group]), 4),
            })
    return out


# ---------- graphs ----------

def save(fig, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def graph_cost_per_query(rows: list[dict], path: Path) -> None:
    """Graph 1. Message: the gate costs a fraction of MMR."""
    means = [np.mean([r["comparisons"] for r in rows_for(rows, m, "all")]) for m in METHODS]
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(
        [LABELS[m] for m in METHODS], means, width=0.55,
        color=[COLOURS[m] for m in METHODS],
    )
    ax.bar_label(bars, labels=[f"{v:.1f}" for v in means], padding=3, color=TEXT)
    ax.set_ylabel("Similarity comparisons per query (average)")
    ax.set_title("Cost per query")
    ax.grid(axis="x", visible=False)
    save(fig, path)


def graph_cost_vs_k(table: list[dict], path: Path) -> None:
    """Graph 2. Message: the gap between MMR and the gate widens as k grows."""
    fig, ax = plt.subplots(figsize=(6.5, 4))
    for method in METHODS:
        pts = [r for r in table if r["method"] == method]
        ks = [r["k"] for r in pts]
        costs = [r["mean_comparisons"] for r in pts]
        ax.plot(ks, costs, marker="o", markersize=7, linewidth=2,
                color=COLOURS[method], label=LABELS[method])
        ax.annotate(f"{costs[-1]:.0f}", (ks[-1], costs[-1]), textcoords="offset points",
                    xytext=(8, -3), color=TEXT)
    ks = sorted({r["k"] for r in table})
    ax.set_xticks(ks)
    ax.set_xlabel("k (chunks returned)")
    ax.set_ylabel("Similarity comparisons per query (average)")
    ax.set_title("Cost as k grows")
    ax.legend(loc="upper left")
    save(fig, path)


def graph_signal_histogram(rows: list[dict], tau: float, path: Path) -> None:
    """Graph 3. Message: most queries need nothing, only the tail past tau is repaired."""
    signals = np.array([r["signal"] for r in rows_for(rows, "gate", "all")])
    width = 0.01
    # Bin edges lined up on tau, so no bar straddles the line.
    lo = tau - width * np.ceil((tau - signals.min()) / width)
    hi = tau + width * np.ceil((signals.max() - tau) / width)
    edges = np.arange(lo, hi + width / 2, width)
    counts, edges = np.histogram(signals, bins=edges)
    lefts = edges[:-1]
    colours = [COLOURS["gate"] if left >= tau - 1e-9 else SHIPPED_GREY for left in lefts]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(lefts, counts, width=width * 0.9, align="edge", color=colours)
    ax.axvline(tau, color=TEXT, linewidth=1.5, linestyle="--")
    ax.annotate(f"tau = {tau:.3f}", (tau, counts.max()), textcoords="offset points",
                xytext=(5, 0), color=TEXT)

    shipped = np.mean(signals <= tau)
    ax.text(0.02, 0.95, f"Shipped as-is: {shipped:.0%}", transform=ax.transAxes,
            color=SHIPPED_GREY, va="top", fontweight="bold")
    ax.text(0.98, 0.95, f"Repaired: {1 - shipped:.0%}", transform=ax.transAxes,
            color=TEXT, va="top", ha="right", fontweight="bold")
    ax.set_xlabel("Gate signal (mean pair similarity of the plain top-k)")
    ax.set_ylabel("Number of queries")
    ax.set_title("Where queries fall")
    ax.grid(axis="x", visible=False)
    save(fig, path)


def graph_tripped_vs_not(rows: list[dict], path: Path) -> None:
    """Graph 4. Dot plot of ILS and relevance, tripped vs not-tripped queries.

    Message: where the gate trips it lands between plain and MMR; where it does not, it
    sits exactly on plain while MMR still moves away, at many times the cost.

    A dot plot rather than bars on purpose. The averages differ only in the second or
    third decimal, so bars from zero all look the same height, and bars on a cut axis
    would exaggerate the gaps. A dot is read by its position, so a zoomed axis is
    honest here. Each group gets one row per method, so dots that share a value (gate
    and plain on not-tripped queries) sit side by side instead of hiding each other.
    """
    groups = [("tripped", "Tripped"), ("not_tripped", "Not tripped")]
    row_offset = {"plain": 0.25, "mmr": 0.0, "gate": -0.25}   # plain on top of each group
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    for ax, (metric, title) in zip(axes, [("ils", "ILS (lower = less redundant)"),
                                          ("relevance", "Relevance (higher = better)")]):
        all_values = []
        for g, (subset, _) in enumerate(groups):
            y_centre = len(groups) - 1 - g                       # first group at the top
            for method in METHODS:
                group = rows_for(rows, method, subset)
                if not group:
                    continue
                value = np.mean([r[metric] for r in group])
                all_values.append(value)
                y = y_centre + row_offset[method]
                ax.scatter(value, y, s=70, color=COLOURS[method], edgecolors=SURFACE,
                           linewidths=1.5, zorder=3, label=LABELS[method] if g == 0 else None)
                ax.annotate(f"{value:.3f}", (value, y), textcoords="offset points",
                            xytext=(9, -3), fontsize=8, color=TEXT)
        # Zoomed axis around the data, the same for both groups so gaps compare directly.
        lo, hi = min(all_values), max(all_values)
        pad = (hi - lo) * 0.25 or 0.005
        ax.set_xlim(lo - pad, hi + pad * 1.6)                    # room for value labels
        n_queries = [len(rows_for(rows, "gate", s)) for s, _ in groups]
        ax.set_yticks(
            [len(groups) - 1 - g for g in range(len(groups))],
            [f"{label}\n({n} queries)" for (_, label), n in zip(groups, n_queries)],
        )
        ax.set_ylim(-0.6, len(groups) - 0.4)
        ax.set_title(title)
        ax.grid(axis="y", visible=False)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def graph_ils_vs_relevance(rows: list[dict], path: Path) -> None:
    """Graph 5. Message: the gate removes redundancy without losing relevance.

    Drawn plain first and gate last. Where the gate did not trip it returns exactly the
    plain set, so its dot lands on top of the plain dot and hides it. That is correct,
    and the note under the title says so. Solid dots with a thin ring instead of
    see-through ones, so overlaps do not blend into new colours.
    """
    fig, ax = plt.subplots(figsize=(6.5, 5))
    for method in METHODS:
        group = rows_for(rows, method, "all")
        ax.scatter([r["ils"] for r in group], [r["relevance"] for r in group], s=30,
                   color=COLOURS[method], edgecolors=SURFACE, linewidths=1,
                   label=LABELS[method])
    ax.text(0.0, 1.01, "Where the gate did not trip, its dot covers the plain dot",
            transform=ax.transAxes, fontsize=8, color=TEXT_SECONDARY)
    ax.set_xlabel("ILS (lower = less redundant)")
    ax.set_ylabel("Relevance (higher = better)")
    ax.set_title("Redundancy vs relevance, one dot per query", pad=16)
    ax.legend(loc="lower right")
    save(fig, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the evaluation and draw the graphs.")
    parser.add_argument("--out", default=None, help="output folder, default from config")
    args = parser.parse_args()

    config = load_config()
    eval_cfg, model_cfg = config["evaluation"], config["model"]
    out = Path(args.out) if args.out else resolve_path(eval_cfg["results_dir"])
    figures = out / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    chunks, embeddings, sim_matrix = build_index(config)
    queries = load_queries(resolve_path(eval_cfg["queries_path"]))
    print(f"embedding {len(queries)} queries")
    query_embs = embed_queries(queries, model_cfg["name"], model_cfg["device"])

    k = config["retrieval"]["k"]
    rows = run_experiment(queries, query_embs, embeddings, sim_matrix, config, k)
    rows_by_k = {k: rows}
    for other_k in eval_cfg["cost_vs_k"]:
        if other_k != k:
            rows_by_k[other_k] = run_experiment(
                queries, query_embs, embeddings, sim_matrix, config, other_k
            )
    k_table = cost_vs_k(dict(sorted(rows_by_k.items())))

    write_csv(out / "per_query.csv", rows)
    write_csv(out / "summary.csv", summarise(rows))
    write_csv(out / "cost_vs_k.csv", k_table)

    graph_cost_per_query(rows, figures / "1_cost_per_query.png")
    graph_cost_vs_k(k_table, figures / "2_cost_vs_k.png")
    graph_signal_histogram(rows, rows[0]["tau"], figures / "3_where_queries_fall.png")
    graph_tripped_vs_not(rows, figures / "4_tripped_vs_not_tripped.png")
    graph_ils_vs_relevance(rows, figures / "5_ils_vs_relevance.png")

    trip_rate = np.mean([r["tripped"] for r in rows_for(rows, "gate", "all")])
    print(f"k={k}: gate tripped on {trip_rate:.0%} of {len(queries)} queries")
    print(f"wrote CSVs to {out} and five graphs to {figures}")


if __name__ == "__main__":
    main()
