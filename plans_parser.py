# -*- coding: utf-8 -*-
"""
Created on Wed Feb 25 12:29:16 2026

Parses output_plans.xml.gz to extract the sequence of real activities
(home / work / leisure) for each person, with their location and timing.

The output is used by timetable_builder.py to assign an activity type
and (x, y) coordinates to each parking window.
"""

import gzip
import xml.etree.ElementTree as ET
import pandas as pd


# Activity types that represent real activities (exclude MATSim internals)
REAL_ACTIVITY_TYPES = {"home", "work", "leisure", "shop", "education", "other"}
IGNORED_TYPES       = {"car interaction", "bike interaction", "pt interaction"}


def parse_plans(plans_path: str) -> pd.DataFrame:
    """
    Parse output_plans.xml.gz and return a DataFrame of real activities.

    Parameters
    ----------
    plans_path : str
        Path to output_plans.xml.gz

    Returns
    -------
    pd.DataFrame with columns:
        person_id       : str
        activity_type   : str   (home / work / leisure / ...)
        link_id         : str
        x               : float (EPSG:2154)
        y               : float (EPSG:2154)
        start_time_s    : float (seconds from midnight, NaN for first activity)
        end_time_s      : float (seconds from midnight, NaN for last activity)
    """

    records = []

    with gzip.open(plans_path, "rb") as f:
        tree = ET.parse(f)
    root = tree.getroot()

    for person in root.iter("person"):
        person_id = person.get("id")

        # Use only the selected plan
        selected_plan = None
        for plan in person.findall("plan"):
            if plan.get("selected") == "yes":
                selected_plan = plan
                break

        if selected_plan is None:
            continue

        for element in selected_plan:
            if element.tag != "activity":
                continue

            activity_type = element.get("type", "")

            # Skip MATSim internal interaction activities
            if activity_type in IGNORED_TYPES:
                continue

            link_id    = element.get("link")
            x          = element.get("x")
            y          = element.get("y")
            start_time = element.get("start_time")   # missing for first activity
            end_time   = element.get("end_time")     # missing for last activity

            records.append({
                "person_id":     person_id,
                "activity_type": activity_type,
                "link_id":       link_id,
                "x":             float(x)  if x  is not None else None,
                "y":             float(y)  if y  is not None else None,
                "start_time_s":  _to_seconds(start_time),  # NaN if missing
                "end_time_s":    _to_seconds(end_time),    # NaN if missing
            })

    df = pd.DataFrame(records)

    # First activity of day: start_time is missing → assign 0
    df["start_time_s"] = df["start_time_s"].fillna(0.0)

    print(f"  → {df['person_id'].nunique():,} persons | "
          f"{len(df):,} activities parsed")
    print(f"  → Activity types: {sorted(df['activity_type'].unique())}")

    return df


def _to_seconds(time_str: str) -> float:
    """
    Convert HH:MM:SS string to seconds from midnight.
    MATSim allows hours > 24 for trips starting after midnight (e.g. 25:30:00).
    Returns NaN if time_str is None or unparseable.
    """
    if time_str is None:
        return float("nan")
    try:
        parts = time_str.strip().split(":")
        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        return float(h * 3600 + m * 60 + s)
    except Exception:
        return float("nan")


def match_activities_to_timetable(
    timetable_df: pd.DataFrame,
    plans_df: pd.DataFrame,
    nodes: dict,        # node_id -> Node (from network_parser)
    links: dict,        # link_id -> Link (from network_parser)
) -> pd.DataFrame:
    """
    Enrich each parked episode in timetable_df with activity_type and (x, y).

    Matching logic:
        1. person_id match  (vehicle_id stripped of ":car")
        2. link_id match
        3. activity start_time_s falls strictly within (t_start, t_end)
           of the parking window

    For unmatched parking windows, activity_type = "unknown" and
    (x, y) are taken from the to_node of the link in the network.

    Parameters
    ----------
    timetable_df : pd.DataFrame
        Output of timetable_builder.py — contains both driving and parked episodes.
    plans_df : pd.DataFrame
        Output of parse_plans().
    nodes : dict
        node_id -> Node dataclass from network_parser.
    links : dict
        link_id -> Link dataclass from network_parser.

    Returns
    -------
    timetable_df with three new columns added to parked episodes:
        activity_type : str
        x             : float
        y             : float
    """

    timetable_df = timetable_df.copy()
    timetable_df["activity_type"] = "unknown"
    timetable_df["x"]             = float("nan")
    timetable_df["y"]             = float("nan")

    # Extract person_id from vehicle_id (only for parked episodes)
    parked_mask = timetable_df["episode_type"] == "parked"
    timetable_df.loc[parked_mask, "person_id"] = (
        timetable_df.loc[parked_mask, "vehicle_id"].str.replace(":car", "", regex=False)
    )

    # Build a lookup: (person_id, link_id) -> list of activities
    plans_lookup = plans_df.groupby(["person_id", "link_id"])

    matched   = 0
    unmatched = 0

    for idx, row in timetable_df[parked_mask].iterrows():
        person_id = row["person_id"]
        link_id   = str(row["link_id"])
        t_start   = row["t_start"]
        t_end     = row["t_end"]

        key = (person_id, link_id)

        if key in plans_lookup.groups:
            candidates = plans_df.loc[plans_lookup.groups[key]]

            # Find activity whose start_time_s falls within the parking window
            match = candidates[
                (candidates["start_time_s"] > t_start) &
                (candidates["start_time_s"] < t_end)
            ]

            if len(match) == 1:
                timetable_df.at[idx, "activity_type"] = match.iloc[0]["activity_type"]
                timetable_df.at[idx, "x"]             = match.iloc[0]["x"]
                timetable_df.at[idx, "y"]             = match.iloc[0]["y"]
                matched += 1
                continue

            # Edge case: multiple matches (same link, same window) — take first
            if len(match) > 1:
                timetable_df.at[idx, "activity_type"] = match.iloc[0]["activity_type"]
                timetable_df.at[idx, "x"]             = match.iloc[0]["x"]
                timetable_df.at[idx, "y"]             = match.iloc[0]["y"]
                matched += 1
                continue

        # No match found — fall back to network coordinates
        unmatched += 1
        if link_id in links:
            to_node_id = links[link_id].to_node
            if to_node_id in nodes:
                timetable_df.at[idx, "x"] = nodes[to_node_id].x
                timetable_df.at[idx, "y"] = nodes[to_node_id].y

    print(f"  → Parked episodes matched: {matched:,} | unmatched (fallback): {unmatched:,}")

    return timetable_df
