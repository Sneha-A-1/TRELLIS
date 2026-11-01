#!/usr/bin/env python3
"""Rebuild data/raw/azure_stats.json from the Azure Functions 2019 release."""
import json, sys
import numpy as np, pandas as pd

if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    cols = [str(i) for i in range(1, 1441)]
    keep, rng = [], np.random.default_rng(42)
    for chunk in pd.read_csv(f"{root}/invocations_per_function_md.anon.d01.csv",
                             usecols=["HashFunction", "Trigger"] + cols,
                             chunksize=40000, low_memory=False):
        v = chunk[cols].to_numpy(dtype=np.float32)
        m = (v.sum(axis=1) >= 500) & (v.sum(axis=1) <= 200000)
        if m.sum():
            sub = chunk[m].reset_index(drop=True); sv = v[m]
            for i in rng.choice(len(sub), size=min(60, len(sub)), replace=False):
                keep.append((sub.loc[i, "HashFunction"],
                             sub.loc[i, "Trigger"], sv[i]))
        if len(keep) >= 300:
            break
    d = pd.read_csv(f"{root}/function_durations_percentiles.anon.d01.csv",
                    low_memory=False)
    sel = d[d.HashFunction.isin({k[0] for k in keep})].copy()
    for c in ["Average", "percentile_Average_50", "percentile_Average_99"]:
        sel[c] = pd.to_numeric(sel[c], errors="coerce")
    sel = sel.dropna(subset=["Average"])
    json.dump({"series": [[float(x) for x in k[2]] for k in keep],
               "triggers": pd.Series([k[1] for k in keep]).value_counts().to_dict(),
               "duration_ms": {"p50": float(sel.percentile_Average_50.median()),
                               "p99": float(sel.percentile_Average_99.median()),
                               "mean": float(sel.Average.median()),
                               "samples": int(len(sel))},
               "n_sampled": len(keep),
               "source": "Azure Functions Trace 2019, day 01"},
              open("data/raw/azure_stats.json", "w"))
    print("sampled", len(keep), "functions")
