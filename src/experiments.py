"""Evaluation of the TRELLIS framework and the CANOPY orchestrator."""

from __future__ import annotations
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

sys.path.insert(0, os.path.dirname(__file__))

import canopy as C
import trellis as TR

RES = os.path.join(os.path.dirname(__file__), "..", "results")
STACKS = ["CLOUD-ONLY", "EDGE-ONLY", "STATIC", "IND-BEST", "CANOPY"]
ABLATIONS = ["CANOPY", "CANOPY-NOFB", "CANOPY-L3", "CANOPY-L4", "IND-BEST"]
METRICS = ("latency_ms", "latency_urgent_ms", "exec_time_s",
           "utilization_pct", "alert_ontime_pct", "deadline_miss_pct",
           "retained_pct", "archive_err_pct", "inversion_pct",
           "fog_share_pct")
LOADS = [1.5, 3.0, 4.5, 5.5, 7.0, 9.0]
NODES = [4, 6, 8, 10, 12]
_C = {}


def data(scale=5.5, minutes=25, seed=42):
    key = (scale, minutes, seed)
    if key not in _C:
        if "soil" not in _C:
            _C["soil"] = TR.load_soil()
        soil = _C["soil"]
        _C[key] = TR.build_tasks(soil, TR.load_azure(), minutes=minutes,
                                 scale=scale, seed=seed)
    return _C[key]


def main_comparison(n_folds=6):
    rows = []
    for k, fold in TR.folds(data(), n_folds):
        for s in STACKS:
            r = C.run_stack(s, fold); r["fold"] = k
            rows.append(r)
    return pd.DataFrame(rows)


def ablation(n_folds=6):
    rows = []
    for k, fold in TR.folds(data(), n_folds):
        for s in ABLATIONS:
            r = C.run_stack(s, fold); r["fold"] = k
            rows.append(r)
    return pd.DataFrame(rows)


def load_sweep():
    rows = []
    for sc in LOADS:
        t = data(scale=sc)
        for s in STACKS:
            r = C.run_stack(s, t); r["scale"] = sc
            r["rate_per_s"] = len(t) / ((t.arrival.max() - t.arrival.min()) / 1000)
            rows.append(r)
    return pd.DataFrame(rows)


def node_sweep():
    rows = []
    t = data()
    for n in NODES:
        for s in STACKS:
            r = C.run_stack(s, t, n_nodes=n); r["nodes"] = n
            rows.append(r)
    return pd.DataFrame(rows)


def main():
    os.makedirs(RES, exist_ok=True)
    cmp_ = main_comparison(); cmp_.to_csv(f"{RES}/comparison_raw.csv", index=False)
    abl = ablation(); abl.to_csv(f"{RES}/ablation_raw.csv", index=False)
    lsw = load_sweep(); lsw.to_csv(f"{RES}/load_sweep.csv", index=False)
    nsw = node_sweep(); nsw.to_csv(f"{RES}/node_sweep.csv", index=False)

    out = {"comparison": {}, "ablation": {}, "load_sweep": {}, "node_sweep": {}}
    for s, v in cmp_.groupby("stack"):
        out["comparison"][s] = {c: round(float(v[c].mean()), 3) for c in METRICS}
        out["comparison"][s]["alert_ci95"] = round(
            float(1.96 * v.alert_ontime_pct.std(ddof=1) / np.sqrt(len(v))), 3)
    for s, v in abl.groupby("stack"):
        out["ablation"][s] = {c: round(float(v[c].mean()), 3) for c in
                              ("alert_ontime_pct", "inversion_pct",
                               "latency_urgent_ms", "archive_err_pct",
                               "retained_pct")}
    for sc, v in lsw.groupby("scale"):
        out["load_sweep"][str(sc)] = {
            s: {c: round(float(g[c].mean()), 3) for c in
                ("alert_ontime_pct", "inversion_pct", "latency_ms",
                 "utilization_pct", "rate_per_s")}
            for s, g in v.groupby("stack")}
    for n, v in nsw.groupby("nodes"):
        out["node_sweep"][str(int(n))] = {
            s: {c: round(float(g[c].mean()), 3) for c in
                ("exec_time_s", "alert_ontime_pct", "utilization_pct")}
            for s, g in v.groupby("stack")}

    def w(a, b, col, frame=cmp_):
        x = frame[frame["stack"] == a][col].to_numpy()
        y = frame[frame["stack"] == b][col].to_numpy()
        return 1.0 if np.allclose(x, y) else float(wilcoxon(x, y).pvalue)

    out["wilcoxon"] = {
        "inversion_canopy_vs_indbest": w("CANOPY", "IND-BEST", "inversion_pct"),
        "alert_canopy_vs_indbest": w("CANOPY", "IND-BEST", "alert_ontime_pct"),
        "urgent_latency_canopy_vs_indbest": w("CANOPY", "IND-BEST", "latency_urgent_ms"),
        "inversion_canopy_vs_l3only": w("CANOPY", "CANOPY-L3", "inversion_pct", abl),
    }

    t = data()
    soil = _C["soil"]
    out["setup"] = {
        "tasks": int(len(t)), "nodes": int(t.node.nunique()),
        "functions": int(t.func.nunique()),
        "rate_per_s": round(len(t) / ((t.arrival.max() - t.arrival.min()) / 1000), 1),
        "urgent_pct": round(100 * float(t.urgent.mean()), 2),
        "demand_ms_mean": round(float(t.demand_ms.mean()), 1),
        "demand_ms_p99": round(float(t.demand_ms.quantile(0.99)), 1),
        "novel_pct": round(100 * float(C._novelty(t).mean()), 2),
        "soil_records": int(len(soil)),
        "soil_urgent_pct": round(100 * float(TR.urgent_mask(soil).mean()), 2),
    }
    with open(f"{RES}/summary.json", "w") as f:
        json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    s = main()
    print(json.dumps(s["comparison"], indent=1))
    print(json.dumps(s["ablation"], indent=1))
    print(json.dumps(s["wilcoxon"], indent=1))
    print(json.dumps(s["setup"], indent=1))
