#!/usr/bin/env python3
"""Reproduce every table and figure of the TRELLIS + CANOPY paper."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
import experiments, figures

if __name__ == "__main__":
    print("[1/2] comparison, ablation, load sweep, node sweep ...")
    s = experiments.main()
    print("[2/2] figures ...")
    figures.fig1_architecture(); figures.fig2_comparison()
    figures.fig3_ablation(); figures.fig4_load(); figures.fig5_nodes()
    c = s["comparison"]
    print("\ndone. results/ and figures/ updated.")
    print("  priority inversion  independent %.2f%% -> TRELLIS %.2f%%"
          % (c["IND-BEST"]["inversion_pct"], c["CANOPY"]["inversion_pct"]))
    print("  urgent latency      independent %.1f ms -> TRELLIS %.1f ms"
          % (c["IND-BEST"]["latency_urgent_ms"], c["CANOPY"]["latency_urgent_ms"]))
