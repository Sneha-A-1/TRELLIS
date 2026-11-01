# Data

Two real sources, paired here for the first time in this series.

## 1. NEON Konza Prairie (agronomic layer)

Soil water content and salinity (DP1.00094.001) and soil temperature
(DP1.00041.001), site **KONA**, Kansas, 1 May – 31 Aug 2023, 30-minute
resolution, five plots at eight depths. Included as `raw/SWS_30_minute.csv`
and `raw/ST_30_minute.csv` (21 MB), so `run_all.py` needs no download.

Joining the products gives 185,711 records across 35 usable nodes; 27.25 %
cross an agronomic bound. Records are used as released — roughly 15 % of raw
rows are empty and only 60 % pass the NEON quality flag, and neither is
repaired.

To re-download (a free API token is required since June 2026):

```python
import neonutilities as nu
for dpid in ["DP1.00094.001", "DP1.00041.001"]:
    nu.zips_by_product(dpid=dpid, site="KONA", startdate="2023-05",
                       enddate="2023-08", package="basic",
                       savepath="./neon", check_size=False, token=TOKEN)
```

## 2. Azure Functions Trace 2019 (workload layer)

<https://github.com/Azure/AzurePublicDataset>, day 01 of the public release
(Shahrad et al., USENIX ATC 2020). `raw/azure_stats.json` holds 120 sampled
functions with their **per-minute invocation counts over the full day** and
the measured duration percentiles of those same functions.

Arrivals come from those counts directly, not from a fitted process, so the
workload keeps the trace's real burstiness (median per-function p99/p50 = 3.0,
peaks of 2,941 invocations per minute) and its heavy-tailed service demand
(p50 109 ms, mean 181 ms, p99 925 ms).

Regenerate with `tools/extract_azure_stats.py` after downloading
`azurefunctions_dataset2019_azurefunctions-dataset2019.tar.xz` from the
release page and extracting `invocations_per_function_md.anon.d01.csv` and
`function_durations_percentiles.anon.d01.csv`.

## Why this pairing

The agronomic value of a task and its computational cost come from
independent real sources, so neither can be tuned to flatter the framework.
