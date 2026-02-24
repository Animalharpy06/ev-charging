# -*- coding: utf-8 -*-
"""
Created on Mon Feb 23 09:08:51 2026

@author: Admin
"""

# ── DIAGNOSTIC Step 2: events_parser.py ──────────────────────────────────
print("\n[DIAGNOSTIC Step 2] Checking event attributes...")

import gzip
import xml.etree.ElementTree as ET

EVENTS_PATH = "//wsl.localhost/Ubuntu-22.04/home/mattiasamore/project/output/simulation_output_01/output_events.xml.gz"

# Events we rely on and attributes we read from each
events_we_use = {
    "PersonEntersVehicle":    ["person", "vehicle"],
    "vehicle enters traffic": ["vehicle", "link"],
    "entered link":           ["vehicle", "link"],
    "vehicle leaves traffic": ["vehicle", "link"],
    "actstart":               ["person", "actType", "link"],
    "actend":                 ["person", "actType", "link"],
}

# Collect one sample per event type
samples = {}
opener = gzip.open if EVENTS_PATH.endswith(".gz") else open
with opener(EVENTS_PATH, "rb") as f:
    for _, elem in ET.iterparse(f, events=("start",)):
        if elem.tag == "event":
            etype = elem.attrib.get("type", "")
            if etype in events_we_use and etype not in samples:     # Only capture event types we actually care about, ignore everything else
                samples[etype] = dict(elem.attrib)
        elem.clear()
        if len(samples) == len(events_we_use):
            break                                                   # stop once we have all samples

print("\nResults:")
for event_type, required_attrs in events_we_use.items():            # Did this event type appear in the file at all?
    if event_type not in samples:
        print(f"\n  ❌ [{event_type}] NOT FOUND IN FILE — check event name!")
        continue

    print(f"\n  ✅ [{event_type}] found. Attributes in file:")      
    for k, v in samples[event_type].items():
        print(f"      {k} = {v}")

    print("Checking required attributes:")
    for attr in required_attrs:                                     # For each event type that was found, verify that every individual attribute we read from it actually exists
        status = "✅" if attr in samples[event_type] else "❌ MISSING"
        print(f"      {attr}: {status}")
