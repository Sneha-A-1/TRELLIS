# TRELLIS + CANOPY: a multi-layered smart agriculture framework

Reference implementation for *"A Multi-Layered Framework for Smart
Agriculture Integrating Edge Intelligence, Fog Orchestration and Cloud
Analytics"*.

Multi-layer frameworks are usually built by picking the best method for each
layer. Each layer is then locally optimal and the pipeline still fails,
because the layers disagree about what matters:

* the **classifier** scores agronomic urgency,
* the **scheduler** orders by deadline,
* the **retention policy** ranks by redundancy.

A node that has been below the wilting point for six hours produces readings
that are agronomically critical and statistically boring. The classifier flags
them, the retention rule discards them, and the pipeline loses an alert one of
its own layers identified. We call this **priority inversion across layers**
and measure it: **70.8 %** in a best-of-breed stack.

**CANOPY** computes one *agronomic value index* at the edge and propagates it
unchanged to fog ordering and cloud retention, with feedback from fog load
back to the edge threshold. Inversion drops to **3.7 %**.

## Quick start

```bash
pip install -r requirements.txt
python run_all.py            # ~6 min, data included
```

Results land in `results/` (CSV + `summary.json`) and `figures/`.

## Layout

| path | contents |
|---|---|
| `src/trellis.py` | NEON loader, Azure workload builder, task stream |
| `src/canopy.py` | value index, the four layers, and every stack compared |
| `src/experiments.py` | comparison, ablation, load sweep, node sweep, Wilcoxon |
| `src/figures.py` | Figs. 1–5 of the paper |
| `tools/extract_azure_stats.py` | rebuild the workload profile from the raw trace |
| `data/raw/` | NEON CSVs + sampled Azure per-function series |

## Datasets

* **NEON KONA** — 185,711 real soil records (water content, ion content, soil
  temperature), 5 plots × 8 depths, 30-min, May–Aug 2023
* **Azure Functions Trace 2019, day 01** — 120 real functions with per-minute
  invocation counts and measured duration percentiles

Arrivals come from the trace's actual counts, and payloads from actual sensor
records walked in per-node time order. See `data/README.md`.

## Results (6 temporal folds, 80,350 tasks at 53.6 tasks/s)

| Stack | Latency (ms) | Urgent (ms) | Util % | Alerts on time | Inversion | Archive err |
|---|---|---|---|---|---|---|
| Cloud-only | 800.0 | 800.0 | 0.0 | 0.00 % | 100.00 % | 0.00 % |
| Edge-only | 48556 | 46581 | 99.8 | 3.69 % | 96.31 % | 0.00 % |
| Static tiering | 48556 | 46581 | 99.8 | 3.69 % | 96.31 % | 0.44 % |
| Independent best | 671.2 | 259.9 | 36.0 | 94.08 % | 70.76 % | 0.69 % |
| **TRELLIS** | **647.5** | **187.0** | 35.0 | **96.32 %** | **3.68 %** | **0.39 %** |

Ablation — which coupling earns what:

| Configuration | Alerts | Inversion | Urgent latency |
|---|---|---|---|
| No sharing | 94.08 % | 70.76 % | 259.9 ms |
| Share at layer 4 only | 94.13 % | 5.87 % | 255.5 ms |
| Share at layer 3 only | 96.32 % | 70.67 % | 187.0 ms |
| Share both, no feedback | 96.22 % | 3.78 % | 190.6 ms |
| **Full CANOPY** | **96.32 %** | **3.68 %** | **187.0 ms** |

Layer-4 sharing removes inversion; layer-3 sharing removes urgent latency;
the two are close to orthogonal.

### Three honest notes

**The alert-rate difference is not significant.** 94.08 % vs 96.32 %,
Wilcoxon p = 0.84. What *is* significant (p = 0.031) is inversion and urgent
latency. The paper says so rather than claiming a win on alerts.

**The feedback loop does almost nothing at moderate load** — 96.32 % vs
96.22 % with it disabled, inside fold variation. It only earns its place
above cluster capacity, where it sustains 90.2 % alert delivery against
58.6 % for the best-of-breed stack.

**Below capacity, all fog-using stacks are indistinguishable** (~96 %). The
framework arbitrates contention; with no contention there is nothing to
arbitrate.

## Citation

Sneha, P. D. Singh, V. Tripathi, "TRELLIS: A Multi-Layered
Framework for Smart Agriculture Integrating Edge Intelligence, Fog
Orchestration and Cloud Analytics" (submitted).

## License

MIT — see `LICENSE`. NEON and Azure data are under their own open licences.
