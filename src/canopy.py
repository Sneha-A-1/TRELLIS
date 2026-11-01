"""Layer policies and the CANOPY cross-layer orchestrator.

The comparison is between *stacks*, not single algorithms. Each stack fixes a
policy for the three active layers:

  CLOUD-ONLY  everything is shipped to the cloud; no fog processing
  EDGE-ONLY   everything is processed at the fog tier, nothing is deferred
  STATIC      static tiering by stream type, EDF at the fog, fixed-rate
              retention -- the common deployed arrangement
  IND-BEST    best-of-breed layers optimised independently: an urgency
              classifier at layer 2, an earliest-deadline scheduler at
              layer 3, and a redundancy-based retention rule at layer 4, each
              computing its own notion of importance
  CANOPY      proposed: one agronomic value index computed at layer 2 and
              propagated unchanged to layers 3 and 4, with cloud-side
              feedback that retunes the layer-2 threshold from fog load

The point of the comparison is IND-BEST versus CANOPY: identical mechanisms,
differing only in whether the layers share a priority signal.
"""

from __future__ import annotations
import heapq
import numpy as np
import pandas as pd

from trellis import EPS, SCALE, SPEED, STREAMS, TAU, TH, exceedance

W_E, W_F = 0.75, 0.25        # exceedance and freshness weights in the AVI
GAMMA = 0.35                 # feedback gain on the layer-2 threshold
THETA0 = 0.38                # nominal layer-2 admission threshold
RETAIN_Q = 0.55              # layer-4 retention budget
CLOUD_RTT = 800.0            # ms, WAN round trip from a rural gateway


# ----------------------------------------------------------------------
def value_index(t: pd.DataFrame) -> np.ndarray:
    """Agronomic Value Index in [0,1], computed once at layer 2.

    Combines how far the reading has passed an agronomic bound with how much
    decision value the elapsed information age has left, using the per-bound
    decay constant of the stream that triggered it.
    """
    ex = t["exceed"].to_numpy(float)
    prox = 1.0 / (1.0 + np.exp(-0.35 * ex))          # 0.5 exactly at the bound
    tau = np.where(np.abs(ex) > 0, TAU["stemp"], TAU["vwc"])
    fresh = np.exp(-t["age_min"].to_numpy(float) / tau)
    return W_E * prox + W_F * prox * fresh


# ----------------------------------------------------------------------
def layer2(stack: str, t: pd.DataFrame, avi: np.ndarray, theta: float):
    """Returns (route_to_fog, priority signal passed downstream)."""
    urg = t["urgent"].to_numpy() == 1
    if stack == "CLOUD-ONLY":
        return np.zeros(len(t), bool), avi
    if stack == "EDGE-ONLY":
        return np.ones(len(t), bool), avi
    if stack == "STATIC":
        # static tiering: water and salinity to fog, temperature to cloud
        ex = t["exceed"].to_numpy()
        return (np.abs(ex) < 1e9) & (t["stemp"].to_numpy() < TH["stemp_hi"]) \
            | urg, avi
    if stack == "IND-BEST":
        # layer 2 decides on urgency alone and forwards only a binary flag
        return urg | (avi >= theta), urg.astype(float)
    return (avi >= theta) | urg, avi                 # CANOPY


def layer3(stack: str, t: pd.DataFrame, to_fog: np.ndarray, sig: np.ndarray,
           n_nodes: int = 6):
    """Fog scheduling. Returns completion times and node busy time."""
    n = len(t)
    arr = t["arrival"].to_numpy(float)
    dem = t["demand_ms"].to_numpy(float)
    dl = t["deadline"].to_numpy(float)
    speed = SPEED[:n_nodes]
    done = np.full(n, np.nan)

    cloud = np.where(~to_fog)[0]
    done[cloud] = arr[cloud] + CLOUD_RTT

    idx = np.where(to_fog)[0]
    if not len(idx):
        return done, np.zeros(n_nodes), 1.0
    order = idx[np.argsort(arr[idx], kind="stable")]

    free = np.zeros(n_nodes)
    busy = np.zeros(n_nodes)
    pend: list = []
    pos = 0
    t_now = arr[order[0]]
    while pos < len(order) or pend:
        j = int(np.argmin(free))
        t_now = max(t_now, free[j])
        while pos < len(order) and arr[order[pos]] <= t_now:
            i = int(order[pos]); pos += 1
            if stack in ("IND-BEST", "STATIC", "EDGE-ONLY"):
                key = (dl[i], arr[i])                    # earliest deadline
            else:                                        # CANOPY
                dens = sig[i] / max(dem[i] / 180.0, 0.05)
                age = 0.0008 * (t_now - arr[i])
                key = (-(dens + age), arr[i])
            heapq.heappush(pend, (key, i))
        if not pend:
            if pos < len(order):
                t_now = arr[order[pos]]
                continue
            break
        _, i = heapq.heappop(pend)
        s = dem[i] / speed[j]
        free[j] = max(free[j], arr[i]) + s
        busy[j] += s
        done[i] = free[j]
    return done, busy, float(free.max())


def _novelty(t: pd.DataFrame) -> np.ndarray:
    """Records that differ from the previous retained sample of the node."""
    n = len(t)
    keep = np.zeros(n, bool)
    nodes = t["node"].to_numpy()
    vals = {s: t[s].to_numpy(float) for s in STREAMS}
    for nd in np.unique(nodes):
        m = np.where(nodes == nd)[0]
        last = {s: vals[s][m[0]] for s in STREAMS}
        keep[m[0]] = True
        for i in m[1:]:
            if any(abs(vals[s][i] - last[s]) > EPS[s] for s in STREAMS):
                keep[i] = True
                for s in STREAMS:
                    last[s] = vals[s][i]
    return keep


def layer4(stack: str, t: pd.DataFrame, sig: np.ndarray, budget=RETAIN_Q):
    """Cloud retention. Returns the retained mask."""
    n = len(t)
    urg = t["urgent"].to_numpy() == 1
    if stack in ("CLOUD-ONLY", "EDGE-ONLY"):
        return np.ones(n, bool)
    if stack == "STATIC":
        keep = np.zeros(n, bool)
        keep[::2] = True                                 # fixed-rate thinning
        return keep | urg
    novel = _novelty(t)
    if stack == "IND-BEST":
        # layer 4 recomputes importance from redundancy alone and never sees
        # the layer-2 signal, so a valuable but unsurprising reading is lost
        return novel
    # CANOPY: the same value index the other layers used, combined with
    # novelty so the archive stays faithful as well as valuable
    k = max(int(budget * n) - int(novel.sum()), 1)
    rest = np.where(~novel)[0]
    keep = novel.copy()
    if len(rest) > k:
        keep[rest[np.argpartition(-sig[rest], k - 1)[:k]]] = True
    else:
        keep[rest] = True
    return keep | urg


# ----------------------------------------------------------------------
def run_stack(stack: str, t: pd.DataFrame, n_nodes: int = 6,
              theta: float = THETA0, feedback: bool = True):
    """Runs the full pipeline and returns end-to-end metrics."""
    avi = value_index(t)
    urg = t["urgent"].to_numpy() == 1
    dl = t["deadline"].to_numpy(float)
    arr = t["arrival"].to_numpy(float)

    th = theta
    if stack.startswith("CANOPY") and stack != "CANOPY-NOFB" and feedback:
        # cloud feedback: raise the admission threshold when the offered fog
        # load exceeds cluster capacity, lower it when the tier is idle
        cap = n_nodes * 1000.0 / max(t["demand_ms"].mean(), 1.0)
        rate = len(t) / max((arr.max() - arr.min()) / 1000.0, 1e-6)
        th = float(np.clip(theta + GAMMA * (rate / cap - 1.0), 0.15, 0.85))

    # ablations share CANOPY's layer 2 but drop the shared signal downstream
    l2 = "CANOPY" if stack.startswith("CANOPY") else stack
    l3 = "IND-BEST" if stack in ("CANOPY-L4",) else \
         ("CANOPY" if stack.startswith("CANOPY") else stack)
    l4 = "IND-BEST" if stack in ("CANOPY-L3",) else \
         ("CANOPY" if stack.startswith("CANOPY") else stack)

    to_fog, sig = layer2(l2, t, avi, th)
    done, busy, makespan = layer3(l3, t, to_fog, sig, n_nodes)
    keep = layer4(l4, t, sig)

    fin = np.isfinite(done)
    lat = done - arr
    ontime = (done <= dl) & fin

    # priority inversion: an urgent item that a downstream layer demotes or
    # discards -- missed deadline at layer 3, or dropped at layer 4
    inversion = urg & (~ontime | ~keep)

    err = []
    nodes = t["node"].to_numpy()
    for s in STREAMS:
        v = t[s].to_numpy(float)
        r = np.empty_like(v)
        for nd in np.unique(nodes):
            m = np.where(nodes == nd)[0]
            kv = keep[m]
            idx = np.where(kv, np.arange(len(m)), -1)
            idx = np.maximum.accumulate(idx)
            idx[idx < 0] = 0
            r[m] = v[m][idx]
        err.append(np.abs(v - r).mean() / SCALE[s])

    return {
        "stack": stack,
        "latency_ms": float(np.nanmean(lat[fin])),
        "latency_urgent_ms": float(np.nanmean(lat[fin & urg])) if (fin & urg).any() else float("nan"),
        "exec_time_s": makespan / 1000.0,
        "utilization_pct": 100.0 * float(busy.sum() / (n_nodes * max(makespan, 1e-9))),
        "alert_ontime_pct": 100.0 * float(ontime[urg].mean()) if urg.any() else 100.0,
        "deadline_miss_pct": 100.0 * float((~ontime[fin]).mean()),
        "retained_pct": 100.0 * float(keep.mean()),
        "archive_err_pct": 100.0 * float(np.mean(err)),
        "inversion_pct": 100.0 * float(inversion[urg].mean()) if urg.any() else 0.0,
        "fog_share_pct": 100.0 * float(to_fog.mean()),
        "theta": th,
    }
