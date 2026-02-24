# -*- coding: utf-8 -*-
"""
Created on Mon Feb 23 11:44:19 2026

@author: Admin
"""

import pandas as pd

# ── Configuration ─────────────────────────────────────────────────────────────
DAY_START = 0
DAY_END   = 86400

# ── Main function ─────────────────────────────────────────────────────────────
def build_timetable(trips_df):
    records = []

    for vehicle_id, group in trips_df.groupby("vehicle_id"):
        group = group.reset_index(drop=True)

        # Parked episode before the first trip
        first_trip = group.iloc[0]
        if first_trip["t_start"] > DAY_START:
            records.append({
                "vehicle_id":   vehicle_id,
                "episode_type": "parked",
                "t_start":      DAY_START,
                "t_end":        first_trip["t_start"],
                "duration_s":   first_trip["t_start"] - DAY_START,
                "link_id":      first_trip["from_link"],
                "distance_m":   None
            })

        for i, row in group.iterrows():

            # Driving episode
            records.append({
                "vehicle_id":   vehicle_id,
                "episode_type": "driving",
                "t_start":      row["t_start"],
                "t_end":        row["t_end"],
                "duration_s":   row["t_end"] - row["t_start"],
                "link_id":      None,
                "distance_m":   row["distance_m"]
            })

            # Parked episode between consecutive trips
            if i + 1 < len(group):
                next_trip = group.iloc[i + 1]
                records.append({
                    "vehicle_id":   vehicle_id,
                    "episode_type": "parked",
                    "t_start":      row["t_end"],
                    "t_end":        next_trip["t_start"],
                    "duration_s":   next_trip["t_start"] - row["t_end"],
                    "link_id":      row["to_link"],
                    "distance_m":   None
                })

        # Parked episode after the last trip
        last_trip = group.iloc[-1]
        if last_trip["t_end"] < DAY_END:
            records.append({
                "vehicle_id":   vehicle_id,
                "episode_type": "parked",
                "t_start":      last_trip["t_end"],
                "t_end":        DAY_END,
                "duration_s":   DAY_END - last_trip["t_end"],
                "link_id":      last_trip["to_link"],
                "distance_m":   None
            })

    timetable = pd.DataFrame(records)
    timetable = timetable.sort_values(["vehicle_id", "t_start"]).reset_index(drop=True)
    return timetable


# To check the results from Step 3 you can paste this in WSL and look the output
# python3 -c "
# import pandas as pd

# df = pd.read_parquet('output/vehicle_timetable.parquet')

# print('=== SHAPE ===')
# print(f'{len(df):,} episodes | {df[\"vehicle_id\"].nunique():,} vehicles')

# print()
# print('=== EPISODE TYPE COUNTS ===')
# print(df['episode_type'].value_counts())

# print()
# print('=== FIRST 10 ROWS (first vehicle) ===')
# first_vehicle = df['vehicle_id'].iloc[0]
# print(df[df['vehicle_id'] == first_vehicle].to_string())

# print()
# print('=== DURATION STATS (seconds) ===')
# print(df.groupby('episode_type')['duration_s'].describe().round(1).to_string())
# "