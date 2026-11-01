"""Generates the five figures of the TRELLIS + CANOPY paper (300 dpi)."""
from __future__ import annotations
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = os.path.join(os.path.dirname(__file__), "..")
RES, FIG = f"{ROOT}/results", f"{ROOT}/figures"
CW = 3.4
plt.rcParams.update({
    "font.family": "serif", "font.size": 7.2, "axes.linewidth": 0.6,
    "xtick.labelsize": 6.6, "ytick.labelsize": 6.6, "legend.fontsize": 6.3,
    "axes.labelsize": 7.4, "axes.titlesize": 7.6, "savefig.dpi": 300,
    "figure.dpi": 300, "lines.linewidth": 1.0, "legend.frameon": False})
GREY = "#4d4d4d"
ORDER = ["CLOUD-ONLY", "EDGE-ONLY", "STATIC", "IND-BEST", "CANOPY"]
NAME = {"CLOUD-ONLY": "cloud-only", "EDGE-ONLY": "edge-only",
        "STATIC": "static tiering", "IND-BEST": "independent best",
        "CANOPY": "TRELLIS/CANOPY"}
COL = {"CLOUD-ONLY": "#cccccc", "EDGE-ONLY": "#a6a6a6", "STATIC": "#7f7f7f",
       "IND-BEST": "#4c72b0", "CANOPY": "#c0392b"}
HAT = {"CLOUD-ONLY": "", "EDGE-ONLY": "//", "STATIC": "..",
       "IND-BEST": "\\\\", "CANOPY": "xx"}
MK = {"CLOUD-ONLY": "v", "EDGE-ONLY": "s", "STATIC": "^", "IND-BEST": "D",
      "CANOPY": "o"}


def _s():
    return json.load(open(f"{RES}/summary.json"))


def fig1_architecture():
    fig, ax = plt.subplots(figsize=(CW, 3.15))
    ax.set_xlim(0, 10); ax.set_ylim(0, 12.2); ax.axis("off")

    def box(x, y, w, h, txt, fc, fs=6.0, bold=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06",
                     linewidth=0.6, edgecolor=GREY, facecolor=fc))
        ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center",
                fontsize=fs, fontweight="bold" if bold else "normal",
                linespacing=1.25)

    def arr(x1, y1, x2, y2, ls="-", c=GREY, lw=0.7):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                     mutation_scale=6, linewidth=lw, linestyle=ls, color=c))

    box(0.15, 10.0, 9.7, 2.05, "", "#f2f2f2")
    ax.text(0.35, 11.85, "LAYER 1  Sensing", fontsize=6.5, fontweight="bold", va="top")
    for k, l in enumerate(["water\ncontent", "ion\ncontent", "soil\ntemperature",
                           "35 nodes\n5 plots"]):
        box(0.45 + 2.36 * k, 10.2, 2.05, 1.15, l, "white", fs=5.5)

    for x in (2.0, 5.0, 8.0):
        arr(x, 10.0, x, 9.15)
    box(0.15, 6.95, 9.7, 2.2, "", "#e8e8e8")
    ax.text(0.35, 8.97, "LAYER 2  Agronomic value index (AVI)", fontsize=6.5,
            fontweight="bold", va="top")
    box(0.45, 7.1, 2.9, 1.3, "exceedance\n$e_i$  (1)", "white", fs=5.4)
    box(3.55, 7.1, 2.9, 1.3, "freshness\n$V_i$  (2)", "white", fs=5.4)
    box(6.65, 7.1, 2.9, 1.3, "$A_i$, tier\n(3), (4)", "#f6dcd9", fs=5.4)
    arr(3.35, 7.75, 3.55, 7.75); arr(6.45, 7.75, 6.65, 7.75)

    arr(8.1, 6.95, 8.1, 4.75, c="#c0392b", lw=1.0)
    ax.text(8.25, 5.9, "one signal\n$A_i$ reused", fontsize=5.2, color="#c0392b")
    arr(2.2, 6.95, 2.2, 4.75)

    box(0.15, 2.55, 9.7, 2.2, "", "#dedede")
    ax.text(0.35, 4.57, "LAYER 3  Fog orchestration", fontsize=6.5,
            fontweight="bold", va="top")
    box(0.45, 2.7, 4.3, 1.3, "value-density order\n$A_i / c_i$  (5)", "white", fs=5.4)
    box(5.05, 2.7, 4.5, 1.3, "capacity-matched\nplacement  (6)", "white", fs=5.4)
    arr(4.75, 3.35, 5.05, 3.35)

    arr(2.2, 2.55, 2.2, 1.95); arr(8.1, 2.55, 8.1, 1.95, c="#c0392b", lw=1.0)
    box(0.15, 0.25, 9.7, 1.7, "", "#f2f2f2")
    ax.text(0.35, 1.8, "LAYER 4  Cloud retention and analytics", fontsize=6.5,
            fontweight="bold", va="top")
    box(0.45, 0.4, 4.3, 1.0, "retain by $A_i$\n+ novelty  (7)", "white", fs=5.4)
    box(5.05, 0.4, 4.5, 1.0, "strategic queries,\nthreshold feedback", "white", fs=5.4)

    arr(0.15, 1.0, 0.15, 8.2, ls=(0, (1.6, 1.2)), c="#7a7a7a")
    ax.text(0.04, 4.6, "load feedback $\\theta$", fontsize=5.1, rotation=90,
            va="center", color="#5a5a5a")
    fig.tight_layout(pad=0.15)
    fig.savefig(f"{FIG}/fig1_architecture.png", bbox_inches="tight")
    plt.close(fig)


def fig2_comparison():
    s = _s()["comparison"]
    fig, ax = plt.subplots(1, 2, figsize=(CW * 2.02, 1.95))
    for i, p in enumerate(ORDER):
        ax[0].bar(i, max(s[p]["alert_ontime_pct"], 0.4), 0.66, color=COL[p],
                  edgecolor="k", linewidth=0.4, hatch=HAT[p],
                  yerr=s[p]["alert_ci95"], capsize=2, error_kw=dict(lw=0.6))
        ax[1].bar(i, s[p]["inversion_pct"], 0.66, color=COL[p], edgecolor="k",
                  linewidth=0.4, hatch=HAT[p])
    ax[0].set_ylabel("Urgent alerts on time (%)"); ax[0].set_ylim(0, 108)
    ax[0].set_title("(a) end-to-end alert delivery")
    ax[1].set_ylabel("Priority inversion (%)"); ax[1].set_ylim(0, 108)
    ax[1].set_title("(b) urgent items lost downstream")
    for a in ax:
        a.set_xticks(range(len(ORDER)))
        a.set_xticklabels([NAME[p] for p in ORDER], fontsize=5.8, rotation=18,
                          ha="right")
        a.grid(axis="y", alpha=0.25, lw=0.4)
    fig.tight_layout(pad=0.3)
    fig.savefig(f"{FIG}/fig2_comparison.png", bbox_inches="tight")
    plt.close(fig)


def fig3_ablation():
    s = _s()["ablation"]
    keys = ["IND-BEST", "CANOPY-L4", "CANOPY-L3", "CANOPY-NOFB", "CANOPY"]
    lab = ["no sharing", "share at\nlayer 4 only", "share at\nlayer 3 only",
           "share both,\nno feedback", "full CANOPY"]
    x = np.arange(len(keys)); w = 0.38
    fig, ax = plt.subplots(figsize=(CW, 1.95))
    ax2 = ax.twinx()
    ax.bar(x - w / 2, [s[k]["inversion_pct"] for k in keys], w,
           color="#4c72b0", edgecolor="k", linewidth=0.4, label="inversion")
    ax2.bar(x + w / 2, [s[k]["latency_urgent_ms"] for k in keys], w,
            color="#c0392b", edgecolor="k", linewidth=0.4, hatch="xx",
            label="urgent latency")
    ax.set_ylabel("Priority inversion (%)", color="#4c72b0")
    ax2.set_ylabel("Urgent latency (ms)", color="#c0392b")
    ax.set_xticks(x); ax.set_xticklabels(lab, fontsize=5.5)
    ax.set_ylim(0, 80); ax2.set_ylim(0, 300)
    ax.grid(axis="y", alpha=0.25, lw=0.4)
    fig.tight_layout(pad=0.2)
    fig.savefig(f"{FIG}/fig3_ablation.png", bbox_inches="tight")
    plt.close(fig)


def fig4_load():
    s = _s()["load_sweep"]
    ks = sorted(s, key=float)
    xs = [s[k]["CANOPY"]["rate_per_s"] for k in ks]
    fig, ax = plt.subplots(1, 2, figsize=(CW * 2.02, 1.95))
    for p in ORDER:
        ax[0].plot(xs, [s[k][p]["alert_ontime_pct"] for k in ks], MK[p] + "-",
                   color=COL[p], ms=3.0, label=NAME[p],
                   mfc="none" if p != "CANOPY" else COL[p])
        ax[1].plot(xs, [max(s[k][p]["latency_ms"], 1) for k in ks], MK[p] + "-",
                   color=COL[p], ms=3.0,
                   mfc="none" if p != "CANOPY" else COL[p])
    ax[1].set_yscale("log")
    ax[0].set_ylabel("Urgent alerts on time (%)")
    ax[0].set_title("(a) alert delivery")
    ax[1].set_ylabel("Mean latency (ms)")
    ax[1].set_title("(b) latency")
    for a in ax:
        a.set_xlabel("Offered load (tasks/s)")
        a.grid(alpha=0.25, lw=0.4)
    ax[0].legend(ncol=5, loc="upper center", bbox_to_anchor=(1.1, 1.40),
                 handlelength=1.1, columnspacing=0.7, fontsize=5.5)
    fig.tight_layout(pad=0.3)
    fig.subplots_adjust(top=0.76)
    fig.savefig(f"{FIG}/fig4_load.png", bbox_inches="tight")
    plt.close(fig)


def fig5_nodes():
    s = _s()["node_sweep"]
    xs = sorted(int(k) for k in s)
    fig, ax = plt.subplots(figsize=(CW, 1.95))
    for p in ORDER:
        ax.plot(xs, [s[str(x)][p]["exec_time_s"] for x in xs], MK[p] + "-",
                color=COL[p], ms=3.0, label=NAME[p],
                mfc="none" if p != "CANOPY" else COL[p])
    ax.set_xlabel("Number of fog nodes"); ax.set_ylabel("Execution time (s)")
    ax.set_xticks(xs); ax.grid(alpha=0.25, lw=0.4)
    ax.legend(ncol=2, loc="upper right", handlelength=1.4, fontsize=5.8)
    fig.tight_layout(pad=0.2)
    fig.savefig(f"{FIG}/fig5_nodes.png", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(FIG, exist_ok=True)
    fig1_architecture(); fig2_comparison(); fig3_ablation()
    fig4_load(); fig5_nodes()
    print("figures written to", FIG)
