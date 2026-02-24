# -*- coding: utf-8 -*-
"""
Created on Mon Feb 23 15:38:26 2026

@author: Admin
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os

# ── Configuration ─────────────────────────────────────────────────────────────
TYPICAL_DAYS_PATH = "//wsl.localhost/Ubuntu-22.04/home/mattiasamore/project/post_processing/TypicalDays.xlsx"
SLOT_DURATION     = 900
N_SLOTS           = 96

def build_profiles():
    ts       = pd.read_excel(TYPICAL_DAYS_PATH, sheet_name="TimeSeries", index_col=[0, 1])
    SolRad_h = ts["SolarRad_glob[W/m2]"].to_numpy()
    Price_h  = ts["ElectricityPrice[€/MWh]"].to_numpy()
    hours_24 = np.arange(24, dtype=float)

    SolRad_avg = np.zeros(N_SLOTS)
    Price_avg  = np.zeros(N_SLOTS)

    for s in range(N_SLOTS):
        t_sub         = np.linspace(s * 0.25, (s + 1) * 0.25, 4, endpoint=False)
        SolRad_avg[s] = np.mean(np.interp(t_sub, hours_24, SolRad_h))
        Price_avg[s]  = np.mean(np.interp(t_sub, hours_24, Price_h))

    return pd.DataFrame({
        "slot":         np.arange(N_SLOTS),
        "t_start":      np.arange(N_SLOTS) * SLOT_DURATION,
        "SolRad_Wm2":   SolRad_avg,
        "Price_EURkWh": Price_avg / 1000
    })

# If you want to see the interpolation uncomment the following section

# if __name__ == "__main__":
#     import os
#     OUTPUT_DIR = "output"
#     os.makedirs(OUTPUT_DIR, exist_ok=True)
#     slot_hours   = np.arange(N_SLOTS) * 0.25
#     hours_24     = np.arange(24, dtype=float)
#     ts           = pd.read_excel(TYPICAL_DAYS_PATH, sheet_name="TimeSeries", index_col=[0, 1])
#     SolRad_h     = ts["SolarRad_glob[W/m2]"].to_numpy()
#     Price_h      = ts["ElectricityPrice[€/MWh]"].to_numpy()

#     profiles_df  = build_profiles()
#     SolRad_avg   = profiles_df["SolRad_Wm2"].to_numpy()
#     Price_avg    = profiles_df["Price_EURkWh"].to_numpy() * 1000

#     SolRad_point = np.interp(slot_hours, hours_24, SolRad_h)
#     Price_point  = np.interp(slot_hours, hours_24, Price_h)

#     profiles_df.to_parquet(os.path.join(OUTPUT_DIR, "input_profiles.parquet"), index=False)

#     fig, ax = plt.subplots(figsize=(14, 5))
#     ax.plot(hours_24, SolRad_h, "o", color="black", label="Original hourly (24 pts)", markersize=8, zorder=3)
#     ax.plot(slot_hours, SolRad_point, "-", color="orange", label="Point interpolation", linewidth=2, alpha=0.7)
#     ax.step(slot_hours, SolRad_avg, where="post", color="red", label="Slot average (used in model)", linewidth=2)
#     ax.set_xlabel("Hour of day")
#     ax.set_ylabel("Solar irradiance [W/m²]")
#     ax.set_title("Solar irradiance — interpolation method comparison")
#     ax.set_xticks(np.arange(0, 25, 2))
#     ax.set_xlim([0, 24])
#     ax.legend()
#     ax.grid(True)
#     plt.tight_layout()
#     plt.savefig(os.path.join(OUTPUT_DIR, "profile_solar.png"), dpi=150)

#     fig, ax = plt.subplots(figsize=(14, 5))
#     ax.plot(hours_24, Price_h, "o", color="black", label="Original hourly (24 pts)", markersize=8, zorder=3)
#     ax.plot(slot_hours, Price_point, "-", color="steelblue", label="Point interpolation", linewidth=2, alpha=0.7)
#     ax.step(slot_hours, Price_avg, where="post", color="darkblue", label="Slot average (used in model)", linewidth=2)
#     ax.set_xlabel("Hour of day")
#     ax.set_ylabel("Electricity price [€/MWh]")
#     ax.set_title("Electricity price — interpolation method comparison")
#     ax.set_xticks(np.arange(0, 25, 2))
#     ax.set_xlim([0, 24])
#     ax.legend()
#     ax.grid(True)
#     plt.tight_layout()
#     plt.savefig(os.path.join(OUTPUT_DIR, "profile_price.png"), dpi=150)
#     plt.show()
