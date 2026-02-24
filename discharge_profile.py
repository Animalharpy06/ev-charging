# -*- coding: utf-8 -*-
"""
Created on Mon Feb 23 14:33:37 2026

@author: Admin
"""

import pandas as pd
import numpy as np

# ── Configuration ─────────────────────────────────────────────────────────────
TIMETABLE_PATH  = "output/vehicle_timetable.parquet"
OUTPUT_PATH     = "output/discharge_profile.parquet"

SLOT_DURATION   = 900          # 15 minutes in seconds
DAY_START       = 0
DAY_END         = 86400
N_SLOTS         = (DAY_END - DAY_START) // SLOT_DURATION   # 96 slots

EFF_EV          = 0.15         # Energy consumption [kWh/km]
CAP_EV          = 60.0         # Battery capacity [kWh]

# ── Load data ─────────────────────────────────────────────────────────────────
timetable = pd.read_parquet(TIMETABLE_PATH)

# ── Build discharge profile ───────────────────────────────────────────────────
def build_discharge_profile(timetable):
    records = []

    for vehicle_id, group in timetable.groupby("vehicle_id"):

        # Initialize arrays for this vehicle (one entry per slot)
        parked_time   = np.zeros(N_SLOTS)   # seconds spent parked in each slot
        driving_time  = np.zeros(N_SLOTS)   # seconds spent driving in each slot
        energy_kWh    = np.zeros(N_SLOTS)   # energy consumed in each slot [kWh]

        for _, row in group.iterrows():
            ep_start    = row["t_start"]
            ep_end      = row["t_end"]
            ep_type     = row["episode_type"]
            ep_duration = row["duration_s"]

            # Find which slots this episode overlaps (among the 96 for each day)
            slot_first = int(ep_start // SLOT_DURATION)                         # Integer division gives the slot index where the episode begins
            slot_last  = int(min(ep_end - 1, DAY_END - 1) // SLOT_DURATION)     # Subtract 1 to avoid counting the next slot when an episode ends exactly on a boundary
                                                                                # min(): clips to the last valid second of the day
            
            for s in range(slot_first, slot_last + 1):
                slot_start = s * SLOT_DURATION
                slot_end   = slot_start + SLOT_DURATION

                # Overlap between episode and this slot [seconds]
                # Example: episode runs 13421→14741s, slot 14 runs 13500→14400s
                # overlap = min(14741, 14400) - max(13421, 13500) = 14400 - 13500 = 900s (full slot is driving)
                
                overlap = min(ep_end, slot_end) - max(ep_start, slot_start)
                overlap = max(overlap, 0)       # Ensures no negative numbers

                if ep_type == "parked":
                    parked_time[s] += overlap                               # Adds the overlap seconds to the correct array

                elif ep_type == "driving":
                    driving_time[s] += overlap

                    # Proportional energy: fraction of trip in this slot
                    if ep_duration > 0:
                        fraction = overlap / ep_duration                    # What share of the total trip falls in this slot
                    else:
                        fraction = 0
                    distance_km     = row["distance_m"] / 1000
                    energy_kWh[s]  += fraction * distance_km * EFF_EV       # Energy attributed to this slot only

        # Apply majority rule for parking flag
        for s in range(N_SLOTS):
            total_time = parked_time[s] + driving_time[s]
            if total_time > 0:
                parked_flag = 1 if parked_time[s] / total_time >= 0.5 else 0
            else:
                parked_flag = 1  # no episode recorded → assume parked

            records.append({
                "vehicle_id":        vehicle_id,
                "slot":              s,
                "t_start":           s * SLOT_DURATION,
                "t_end":             (s + 1) * SLOT_DURATION,
                "parked":            parked_flag,
                "energy_consumed_kWh": round(energy_kWh[s], 6)
            })

    return pd.DataFrame(records)

# ── Run and save ───────────────────────────────────────────────────────────────
# This block only runs when executing discharge_profile.py directly
# It is ignored when imported by run_pipeline.py
if __name__ == "__main__":
    import os
    OUTPUT_DIR = "output"
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    timetable = pd.read_parquet(os.path.join(OUTPUT_DIR, "vehicle_timetable.parquet"))
    print("Building discharge profile...")
    df = build_discharge_profile(timetable)
    df.to_parquet(os.path.join(OUTPUT_DIR, "discharge_profile.parquet"))

    n_vehicles = df["vehicle_id"].nunique()
    total_energy = df["energy_consumed_kWh"].sum()
    avg_daily_km = (total_energy / n_vehicles) / EFF_EV

    print(f"  → {n_vehicles:,} vehicles | {N_SLOTS} slots per vehicle")
    print(f"  → Total energy consumed: {total_energy:.1f} kWh")
    print(f"  → Avg daily distance per vehicle: {avg_daily_km:.1f} km")
    print(df[df["vehicle_id"] == df["vehicle_id"].iloc[0]].to_string())

