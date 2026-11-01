"""TRELLIS: a multi-layered smart agriculture framework.

Two real sources drive the evaluation.

Layer-1 sensing - NEON Konza Prairie Agricultural Site (KONA), Kansas,
    1 May - 31 Aug 2023. DP1.00094.001 soil water content and salinity,
    DP1.00041.001 soil temperature, 30-minute resolution, five plots at eight
    depths. Every task carries one of these 185 711 real records and its
    urgency follows agronomic bounds.

Layer-3 workload - Azure Functions Trace 2019, day 01
    (github.com/Azure/AzurePublicDataset; Shahrad et al., USENIX ATC 2020).
    120 real functions sampled with their per-minute invocation counts over a
    full day (median burstiness p99/p50 = 3.0, peaks to 2941 invocations per
    minute) and their measured execution-duration percentiles (p50 109 ms,
    mean 181 ms, p99 925 ms). Arrivals and service demands are taken from
    these series rather than from a fitted distribution.

The framework itself has four layers:
    1 sensing        real soil records, tagged at the edge
    2 classification agronomic value index and tier assignment
    3 fog            orchestrated task allocation
    4 cloud          retention, strategic queries, feedback to layer 2
"""

from __future__ import annotations

import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
RAW = os.path.join(ROOT, "data", "raw")

STREAMS = ("vwc", "sic", "stemp")
DT_MIN = 30.0

# agronomic bounds, measured from this site's distributions
TH = {"vwc_lo": 0.10, "sic_hi": 1800.0, "stemp_hi": 30.0, "stemp_lo": 14.0}
# how fast each bound's decision value decays (minutes)
TAU = {"vwc": 90.0, "sic": 180.0, "stemp": 30.0}
# retention tolerance per stream, physical units
EPS = {"vwc": 0.004, "sic": 12.0, "stemp": 0.20}
SCALE = {"vwc": 0.136, "sic": 396.0, "stemp": 5.13}

SPEED = np.tile(np.array([0.70, 0.85, 1.00, 1.15, 1.30, 1.50]), 3)
DEADLINE_URGENT = 600.0   # actuator control loop
DEADLINE_ROUTINE = 5000.0


# ----------------------------------------------------------------------
def load_soil(sws_csv: str = None, st_csv: str = None) -> pd.DataFrame:
    sws_csv = sws_csv or os.path.join(RAW, "SWS_30_minute.csv")
    st_csv = st_csv or os.path.join(RAW, "ST_30_minute.csv")
    sws = pd.read_csv(sws_csv, low_memory=False)
    st = pd.read_csv(st_csv, low_memory=False)
    m = sws.merge(st, on=["startDateTime", "horizontalPosition",
                          "verticalPosition"], how="inner")
    m = m.dropna(subset=["VSWCMean", "soilTempMean"]).copy()
    m["VSICMean"] = m["VSICMean"].ffill().bfill()
    m["ts"] = pd.to_datetime(m["startDateTime"])
    t0 = m["ts"].min()
    df = pd.DataFrame({
        "t": ((m["ts"] - t0).dt.total_seconds() / (60 * DT_MIN)).round().astype(int),
        "plot": m["horizontalPosition"].astype(int),
        "depth": m["verticalPosition"].astype(int),
        "vwc": m["VSWCMean"].to_numpy(float),
        "sic": m["VSICMean"].to_numpy(float),
        "stemp": m["soilTempMean"].to_numpy(float),
    })
    df["node"] = df["plot"] * 100 + (df["depth"] - 500)
    return df.sort_values(["t", "node"]).reset_index(drop=True)


def load_azure(path: str = None) -> dict:
    path = path or os.path.join(RAW, "azure_stats.json")
    with open(path) as f:
        return json.load(f)


# ----------------------------------------------------------------------
def exceedance(df: pd.DataFrame) -> np.ndarray:
    """Signed distance past the nearest agronomic bound, in tolerance units.

    Positive means a bound is already crossed; the magnitude says how far.
    """
    return np.vstack([
        (TH["vwc_lo"] - df["vwc"].to_numpy(float)) / EPS["vwc"],
        (df["sic"].to_numpy(float) - TH["sic_hi"]) / EPS["sic"],
        (df["stemp"].to_numpy(float) - TH["stemp_hi"]) / EPS["stemp"],
        (TH["stemp_lo"] - df["stemp"].to_numpy(float)) / EPS["stemp"],
    ]).max(axis=0)


def urgent_mask(df: pd.DataFrame) -> np.ndarray:
    return exceedance(df) > 0


# ----------------------------------------------------------------------
def build_tasks(soil: pd.DataFrame, az: dict, minutes: int = 45,
                scale: float = 0.55, seed: int = 42) -> pd.DataFrame:
    """One task per invocation in the sampled Azure per-function series.

    Each minute of the trace contributes its measured invocation count; the
    arrival instants inside the minute are uniform, the service demand is
    drawn from the trace's duration distribution, and the payload is a real
    NEON record.
    """
    rng = np.random.default_rng(seed)
    series = np.array(az["series"], dtype=float)        # functions x 1440
    n_fun = series.shape[0]
    start = rng.integers(0, 1440 - minutes)
    window = series[:, start:start + minutes]

    d50 = az["duration_ms"]["p50"]
    d99 = az["duration_ms"]["p99"]
    sigma = max(np.log(max(d99, d50 + 1) / max(d50, 1)) / 2.326, 0.25)

    arrivals, demands, fun = [], [], []
    for f in range(n_fun):
        for mi in range(minutes):
            k = int(round(window[f, mi] * scale))
            if k <= 0:
                continue
            a = (mi * 60_000.0) + np.sort(rng.uniform(0, 60_000.0, k))
            arrivals.append(a)
            demands.append(rng.lognormal(np.log(max(d50, 1)), sigma, k))
            fun.append(np.full(k, f))
    arrivals = np.concatenate(arrivals)
    demands = np.clip(np.concatenate(demands), 5.0, 4000.0)
    fun = np.concatenate(fun)
    o = np.argsort(arrivals)
    arrivals, demands, fun = arrivals[o], demands[o], fun[o]

    # each function reports for one sensor node, and successive tasks of that
    # function walk that node's real record sequence in order, so per-node
    # redundancy and temporal structure are those of the NEON series
    nodes = np.sort(soil["node"].unique())
    fun_node = nodes[rng.integers(0, len(nodes), n_fun)]
    by_node = {nd: soil[soil["node"] == nd].reset_index(drop=True)
               for nd in nodes}
    cursor = {nd: int(rng.integers(0, max(len(by_node[nd]) - 1, 1)))
              for nd in nodes}

    rec = np.empty(len(arrivals), int)
    nd_of = np.empty(len(arrivals), int)
    for k in range(len(arrivals)):
        nd = fun_node[int(fun[k])]
        nd_of[k] = nd
        c = cursor[nd]
        rec[k] = c
        cursor[nd] = (c + 1) % len(by_node[nd])

    vwc = np.empty(len(arrivals)); sic = np.empty(len(arrivals))
    stp = np.empty(len(arrivals)); stt = np.empty(len(arrivals), int)
    plot = np.empty(len(arrivals), int)
    for nd in nodes:
        m = np.where(nd_of == nd)[0]
        if not len(m):
            continue
        b = by_node[nd]
        vwc[m] = b["vwc"].to_numpy()[rec[m]]
        sic[m] = b["sic"].to_numpy()[rec[m]]
        stp[m] = b["stemp"].to_numpy()[rec[m]]
        stt[m] = b["t"].to_numpy()[rec[m]]
        plot[m] = b["plot"].to_numpy()[rec[m]]

    t = pd.DataFrame({
        "arrival": arrivals, "demand_ms": demands, "func": fun,
        "node": nd_of, "plot": plot, "vwc": vwc, "sic": sic, "stemp": stp,
        "sensor_t": stt,
    })
    t["exceed"] = exceedance(t)
    t["urgent"] = (t["exceed"] > 0).astype(int)
    # information age at the moment the task is raised
    t["age_min"] = np.clip(rng.exponential(12.0, len(t)), 0.0, 90.0)
    t["deadline"] = t["arrival"] + np.where(t["urgent"] == 1,
                                            DEADLINE_URGENT, DEADLINE_ROUTINE)
    return t.reset_index(drop=True)


def folds(t: pd.DataFrame, n: int = 6):
    """Contiguous minute-blocks of the trace window."""
    edges = np.linspace(t["arrival"].min(), t["arrival"].max() + 1, n + 1)
    for k in range(n):
        m = (t["arrival"] >= edges[k]) & (t["arrival"] < edges[k + 1])
        sub = t[m].copy()
        sub["arrival"] -= edges[k]
        sub["deadline"] -= edges[k]
        yield k, sub.reset_index(drop=True)
