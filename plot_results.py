# -*- coding: utf-8 -*-
"""
Created on Mon Feb 23 17:05:16 2026

@author: Admin
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os

# ── Configuration ─────────────────────────────────────────────────────────────
RESULTS_PATH  = "output/optimization_results.parquet"
OUTPUT_DIR    = "output"
DT            = 900 / 3600
N_SLOTS       = 96

def plot_results():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    res   = pd.read_parquet(RESULTS_PATH)
    hours = np.arange(N_SLOTS) * 0.25

    fig, ax = plt.subplots(figsize=(14, 6))
    fig.suptitle("EV Fleet — Cumulative Charging Power vs PV Production",
                 fontsize=13, fontweight="bold")

    ax.step(hours, res["PPV_kW"],      where="post", color="gold",     linewidth=2.5,
            label="PV production [kW]")
    ax.step(hours, res["total_Pc_kW"], where="post", color="steelblue", linewidth=2.5,
            label="Total charging demand [kW]")
    ax.step(hours, res["P_imp_kW"],    where="post", color="tomato",   linewidth=1.8,
            linestyle="--", label="Grid import [kW]")

    # Fill area where PV covers charging
    pv   = res["PPV_kW"].to_numpy()
    pc   = res["total_Pc_kW"].to_numpy()
    ax.fill_between(hours, np.minimum(pv, pc), step="post",
                    color="gold", alpha=0.25, label="PV covering charge")
    # Fill area where grid must supplement
    ax.fill_between(hours, np.maximum(pc - pv, 0), step="post",
                    color="tomato", alpha=0.20, label="Grid supplement")

    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Power [kW]")
    ax.set_xticks(np.arange(0, 25, 2))
    ax.set_xlim([0, 24])
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.4)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "results_charging_pv.png"), dpi=150)
    plt.show()
    print("  → Saved results_charging_pv.png")


if __name__ == "__main__":
    plot_results()
