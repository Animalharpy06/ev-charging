Here is the full README text ready to paste:

text
# EV Fleet Smart Charging Optimization Pipeline

This pipeline processes urban mobility simulation outputs (EQASim/MATSim) to
optimize the smart charging of an electric vehicle (EV) fleet, integrating
rooftop photovoltaic (PV) generation and time-varying electricity pricing.
It minimizes the daily electricity cost of charging 1,129 EVs over a
representative typical day.

---

## Repository Structure

ev-charging/
├── data/ # Input data (NOT included in the repo — see below)
├── output/ # Generated automatically at runtime
├── run_pipeline.py # Main entry point — runs all steps in sequence
├── network_parser.py
├── events_parser.py
├── timetable_builder.py
├── discharge_profile.py
├── prepare_profiles.py
├── optimize.py
├── plot_results.py
├── config.yaml # Your local config (NOT in repo — see below)
├── config.yaml.example # Template for config.yaml
├── requirements.txt
└── README.md

text

---

## Prerequisites

### 1. Python environment

Install all required packages:

```bash
pip install -r requirements.txt
A working Gurobi installation with a valid license is required for Step 5
(optimization). Academic licenses are available for free at
gurobi.com.

2. EQASim/MATSim simulation outputs
The pipeline reads four files produced by an EQASim/MATSim simulation run.
These are not included in the repository and must be provided by the user.
Place them (or point to them via config.yaml) in your local EQASim output folder:

File	Description
output_network.xml.gz	Road network (nodes and links)
output_events.xml.gz	Agent activity and trip events
output_plans.xml.gz	Agent daily plans
output_allVehicles.xml	Vehicle definitions
3. Typical Days spreadsheet
The solar irradiance and electricity price profiles are read from an Excel file:

File	Description
TypicalDays.xlsx	Hourly solar irradiance (W/m²) and electricity price (€/MWh)
Place this file in your local data/ folder (path configured in config.yaml).

Configuration
The pipeline uses a config.yaml file to define all machine-specific paths.
This file is not tracked by Git (listed in .gitignore) because paths
differ between machines.

Setup steps
bash
# 1. Copy the example template
cp config.yaml.example config.yaml

# 2. Open config.yaml and fill in your own paths
config.yaml reference
text
# ── Option A: running from a Linux / WSL terminal ────────────────────────────
eqasim_output:   "/home/YOUR_USERNAME/research/eqasim-france/output"
typical_days:    "/home/YOUR_USERNAME/research/ev-charging/data/TypicalDays.xlsx"
pipeline_output: "/home/YOUR_USERNAME/research/ev-charging/output"

# ── Option B: running from Spyder on Windows (WSL paths) ─────────────────────
# eqasim_output:   "//wsl.localhost/Ubuntu-22.04/home/YOUR_USERNAME/research/eqasim-france/output"
# typical_days:    "//wsl.localhost/Ubuntu-22.04/home/YOUR_USERNAME/research/ev-charging/data/TypicalDays.xlsx"
# pipeline_output: "//wsl.localhost/Ubuntu-22.04/home/YOUR_USERNAME/research/ev-charging/output"
Uncomment the option that matches your setup and replace YOUR_USERNAME with
your system username.

Folder Setup
The output/ folder is created automatically when the pipeline runs.
The data/ folder must be created manually and populated with the input files:

bash
mkdir -p data output
# Then place TypicalDays.xlsx inside data/
Running the Pipeline
bash
python3 run_pipeline.py
All intermediate and final results are saved as .parquet files in the
output/ folder.

Pipeline Overview
All steps are orchestrated sequentially by run_pipeline.py.

Step 1 — Network Parser (network_parser.py)
Parses the MATSim road network and builds a link-length lookup table.
Output: output/network_links.parquet

Step 2 — Events Parser (events_parser.py)
Parses agent-level trip and activity events from the MATSim output.
Output: output/trips_raw.parquet, output/activities_raw.parquet

Step 3 — Timetable Builder (timetable_builder.py)
Builds a per-vehicle daily timetable of driving and parking episodes.
Output: output/vehicle_timetable.parquet

Step 4a — Discharge Profile (discharge_profile.py)
Converts the vehicle timetable into a 96-slot (15-min resolution) energy
consumption and parking availability profile for each vehicle.

Parameter	Value
Slot duration	900 s (15 min)
Slots per day	96
EV efficiency	0.15 kWh/km
Battery capacity	60 kWh
Output: output/discharge_profile.parquet

Step 4b — Input Profiles (prepare_profiles.py)
Interpolates hourly solar irradiance and electricity price data from
TypicalDays.xlsx onto the 96-slot resolution using slot-average
interpolation (4 sub-samples per slot).
Output: output/input_profiles.parquet

Step 5 — Gurobi LP Optimization (optimize.py)
Solves a linear programming model to find the cost-optimal charging
schedule for the entire fleet over one representative day.

System parameters
Parameter	Value
Number of vehicles	1,129
Time slots	96 × 15 min
Battery capacity	60 kWh
Max charging power	11 kW (AC Type 2)
SOC bounds	15% – 90% of capacity
Charging efficiency	90% (round-trip)
Self-discharge	0.05%/h
PV installed capacity	1,000 kW
Objective
Minimize total daily grid electricity cost [€]:

min
⁡
∑
t
(
P
imp
[
t
]
⋅
c
buy
[
t
]
−
P
exp
[
t
]
⋅
c
sell
)
⋅
Δ
t
min∑ 
t
 (P 
imp
 [t]⋅c 
buy
 [t]−P 
exp
 [t]⋅c 
sell
 )⋅Δt

where $\Delta t = 0.25$ h and $c_{\text{sell}} = 0.008$ €/kWh.

Output: output/optimization_results.parquet, output/soc_results.parquet

Step 6 — Result Visualization (plot_results.py)
Generates plots of the optimized charging schedule, SOC profiles, and
grid import/export curves.

Notes
config.yaml is machine-specific and must never be committed to Git.

The output/ folder is also excluded from Git (auto-generated at runtime).

Gurobi must be activated on your machine before running Step 5.

text

***

A few things to double-check before pasting:
- **Number of vehicles (1,129)** — confirm this matches your current simulation run, as it may change between EQASim scenarios.
- **`output_plans.xml.gz`** — it appears in your `run_pipeline.py` as `PLANS_PATH` but I didn't see it used downstream yet; you can remove it from the table if it's not actually consumed.
- The `data/` folder is visible in your project  but excluded from the repo, so the manual `mkdir` instruction is necessary.[1]