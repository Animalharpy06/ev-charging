\# EV Fleet Smart Charging Optimization Pipeline



This pipeline processes urban mobility simulation outputs to optimize the

smart charging of an electric vehicle (EV) fleet, integrating rooftop

photovoltaic (PV) generation and grid electricity pricing.

It is designed to minimize the daily electricity cost of charging 1,129

EVs, leveraging solar energy and time-varying electricity prices.



---



\## Pipeline Overview



The pipeline is composed of five sequential steps, all orchestrated by

`run\_pipeline.py`. Each step reads from and writes to the `output/`

folder using `.parquet` files for efficient data exchange.



---



\### Step 3 — Typical Day Extraction (`typical\_days.py`)



Processes raw mobility simulation data (from EQASim/MATSim) to extract

a representative typical day for the EV fleet. Outputs a structured

dataset of vehicle activity used as input for all downstream steps.



\*\*Output:\*\* `output/typical\_days.parquet`



---



\### Step 4 — Discharge Profile Builder (`discharge\_profile.py`)



Converts the typical day activity data into a per-vehicle, per-slot

energy profile. The day is discretized into \*\*96 time slots of 15

minutes each\*\* (900 seconds). For each vehicle and each slot, it

computes:



\- `parked` — whether the vehicle is available for charging (1/0)

\- `energy\_consumed\_kWh` — energy consumed by driving in that slot \[kWh]



\*\*Output:\*\* `output/discharge\_profile.parquet`



---



\### Step 4b — Input Profiles Builder (`prepare\_profiles.py`)



Interpolates hourly solar irradiance and electricity price data (from

`TypicalDays.xlsx`) onto the 96-slot 15-minute resolution used by the

optimizer. Uses a \*\*slot-average interpolation\*\* method: for each slot,

four sub-points are sampled within the slot window and averaged. This

ensures energy consistency between the hourly source data and the

15-minute model resolution.



Electricity price is converted from €/MWh to €/kWh. Solar irradiance

remains in W/m².



\*\*Output:\*\* `output/input\_profiles.parquet`



---



\### Step 5 — Gurobi LP Optimization (`optimize.py`)



Formulates and solves a \*\*linear programming (LP)\*\* model using Gurobi

to find the optimal charging schedule for the entire EV fleet over one

representative day.



\#### System parameters

| Parameter | Value |

|---|---|

| Number of vehicles | 1,129 |

| Time slots | 96 × 15 min |

| EV battery capacity | 60 kWh |

| Max charging power | 11 kW (AC Type 2) |

| SOC bounds | 15% – 90% of capacity |

| Round-trip charging efficiency | 90% |

| Self-discharge | 0.05%/h |

| PV installed capacity | 1,000 kW |



\#### Decision variables

\- `Pc\[v, t]` — charging power of vehicle `v` in slot `t` \[kW]

\- `SOC\[v, t]` — state of charge of vehicle `v` at start of slot `t` \[kWh]

\- `P\_imp\[t]` — total grid import power in slot `t` \[kW]

\- `P\_exp\[t]` — total grid export power in slot `t` \[kW]



\#### Constraints

1\. \*\*No charging when driving\*\* — `Pc\[v,t] = 0` if vehicle not parked

2\. \*\*SOC dynamics\*\* — energy balance per vehicle per slot \[kWh]:

&nbsp;  `SOC\[v,t+1] = SOC\[v,t] × (1 − sd) + Pc\[v,t] × η × Δt − E\_cons\[v,t]`

3\. \*\*Cyclic condition\*\* — each vehicle ends the day with at least as

&nbsp;  much charge as it started: `SOC\[v,96] ≥ SOC\[v,0]`

4\. \*\*Power balance\*\* — per slot \[kW]:

&nbsp;  `PPV\[t] + P\_imp\[t] − P\_exp\[t] = Σ\_v Pc\[v,t]`



\#### Objective

Minimize total daily grid electricity cost \[€]:



`min Σ\_t ( P\_imp\[t] × c\_buy\[t] − P\_exp\[t] × c\_sell ) × Δt`



where `Δt = 0.25 h`, `c\_buy\[t]` is the time-varying buy price \[€/kWh],

and `c\_sell = 0.008 €/kWh` is the fixed feed-in tariff.



\*\*Note:\*\* PV generation cost (LCOE) is not yet included in the

objective — marked as TODO.



\*\*Output:\*\* `output/optimization\_results.parquet`, `output/soc\_results.parquet`



---



\## Running the pipeline



```bash

python3 run\_pipeline.py



