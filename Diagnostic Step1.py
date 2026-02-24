# -*- coding: utf-8 -*-
"""
Created on Mon Feb 23 09:06:13 2026

@author: Admin
"""

# ── DIAGNOSTIC Step 1: network_parser.py ─────────────────────────────────
print("\n[DIAGNOSTIC Step 1] Checking network file structure...")

import gzip
import xml.etree.ElementTree as ET

NETWORK_PATH = "//wsl.localhost/Ubuntu-22.04/home/mattiasamore/project/output/simulation_output_01/output_network.xml.gz"

node_sample = None
link_sample = None

opener = gzip.open if NETWORK_PATH.endswith(".gz") else open
with opener(NETWORK_PATH, "rb") as f:
    for _, elem in ET.iterparse(f, events=("start",)):
        if elem.tag == "node" and node_sample is None:      # Only capture the first node we see
            node_sample = dict(elem.attrib)                 # Converts the XML attributes into a plain Python dictionary so we can inspect them freely
        if elem.tag == "link" and link_sample is None:      # Only capture the first link we see
            link_sample = dict(elem.attrib)                 # Converts the XML attributes into a plain Python dictionary so we can inspect them freely
        if node_sample and link_sample:
            break                                           # Stop as soon as we have both samples
        elem.clear()

print("\nFirst <node> attributes found:")
for k, v in node_sample.items():
    print(f"  {k} = {v}")

print("\nFirst <link> attributes found:")
for k, v in link_sample.items():
    print(f"  {k} = {v}")

print("\nAttributes we rely on in network_parser.py:")
print("  <node> : id, x, y")
print("  <link> : id, from, to, length, freespeed, capacity, modes")

print("\nChecking <node>:")
for attr in ["id", "x", "y"]:
    status = "✅" if attr in node_sample else "❌ MISSING"    # For each attribute name that network_parser.py uses, we check if it actually exists in the sample we captured
    print(f"  {attr}: {status}")

print("\nChecking <link>:")
for attr in ["id", "from", "to", "length", "freespeed", "capacity", "modes"]:
    status = "✅" if attr in link_sample else "⚠ missing (has default fallback)"     # For each attribute name that network_parser.py uses, we check if it actually exists in the sample we captured
    print(f"  {attr}: {status}")
