# -*- coding: utf-8 -*-
"""
Created on Mon Feb 23 16:03:51 2026

@author: Admin
"""

import numpy as np
import pandas as pd
import gurobipy as gp
from gurobipy import GRB
import os

# ── Configuration ─────────────────────────────────────────────────────────────
DISCHARGE_PATH  = "output/discharge_profile.parquet"
PROFILES_PATH   = "output/input_profiles.parquet"
OUTPUT_DIR      = "output"

SLOT_DURATION   = 900           # seconds
DT              = SLOT_DURATION / 3600   # hours = 0.25
N_SLOTS         = 96
CAP_PV          = 1200.0        # kW
CAP_EV          = 60.0          # kWh
ETA_C           = 0.9           # round-trip efficiency
ETA_SQRT        = ETA_C ** 0.5  # one-way charging efficiency
P_MAX           = 11.0          # kW — max charging power per vehicle
SOC_MIN         = 0.15          # 15%
SOC_MAX         = 0.90          # 95%
SD_EV           = 0.0005 / 3600 # self-discharge [1/s] → divide by 3600 to get [1/h]... 
                                 # actually kept as [1/h]: 0.05%/h = 0.0005 [1/h]
SD_EV_PER_SLOT  = 0.0005 * DT   # dimensionless loss per slot = 0.000125
C_SELL          = 0.008          # €/kWh — fixed sell price

def run_optimization():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── Load data ─────────────────────────────────────────────────────────────
    discharge = pd.read_parquet(DISCHARGE_PATH)
    profiles  = pd.read_parquet(PROFILES_PATH)
    


    vehicles  = discharge["vehicle_id"].unique()
    V         = len(vehicles)
    vid_map   = {v: i for i, v in enumerate(vehicles)}

    # Parked[v, t] and E_consumed[v, t] in kWh
    Parked = np.zeros((V, N_SLOTS), dtype=int)
    E_cons = np.zeros((V, N_SLOTS))                 # [kWh] already from discharge_profile

    for _, row in discharge.iterrows():
        v = vid_map[row["vehicle_id"]]
        t = int(row["slot"])
        Parked[v, t] = int(row["parked"])
        E_cons[v, t] = row["energy_consumed_kWh"]   # [kWh] consumed in that 15-min slot

    # Solar and price profiles
    SolRad = profiles["SolRad_Wm2"].to_numpy()       # [W/m²]
    C_buy  = profiles["Price_EURkWh"].to_numpy()     # [€/kWh]

    # PV power output [kW] — already a power, no DT needed here
    PPV = CAP_PV * SolRad / 1000.0                   # [kW]

    # ── Gurobi model ──────────────────────────────────────────────────────────
    m = gp.Model("EV_PV_Grid")
    m.Params.OutputFlag    = 1
    m.Params.MIPGap        = 1e-4
    m.Params.TimeLimit     = 3000   # seconds

    # ── Decision variables ────────────────────────────────────────────────────
    # Charging power [kW] per vehicle per slot
    Pc  = m.addVars(V, N_SLOTS, lb=0.0, name="Pc")

    # SOC [kWh] per vehicle per slot (state at START of slot t)
    SOC = m.addVars(V, N_SLOTS + 1, lb=CAP_EV * SOC_MIN, ub=CAP_EV * SOC_MAX, name="SOC")

    # Grid import/export [kW] per slot (aggregated)
    P_imp = m.addVars(N_SLOTS, lb=0.0, name="P_imp")
    P_exp = m.addVars(N_SLOTS, lb=0.0, name="P_exp")

    # ── Constraints ───────────────────────────────────────────────────────────

    # 1. Charging only when parked
    m.addConstrs(Pc[v, t] <= P_MAX * Parked[v, t] for v in range(V) for t in range(N_SLOTS))

    # 2. SOC dynamics — all terms in [kWh]
    #    SOC[v, t+1] = SOC[v, t] * (1 - SD_EV_PER_SLOT)
    #                + Pc[v, t] * ETA_SQRT * DT    ← [kW] * [h] = [kWh]
    #                - E_cons[v, t]                ← already [kWh]
    m.addConstrs(
    (SOC[v, t + 1] == SOC[v, t] * (1 - SD_EV_PER_SLOT) + Pc[v, t] * ETA_SQRT * DT - E_cons[v, t]
     for v in range(V) for t in range(N_SLOTS)), name="soc_dyn")


    # 3. Cyclic condition — SOC at end of day = SOC at start
    m.addConstrs((SOC[v, N_SLOTS] == SOC[v, 0] for v in range(V)), name="cyclic")

    # 4. Power balance per slot [kW] — DT cancels on both sides
    #    PPV[t] + P_imp[t] - P_exp[t] = sum_v Pc[v, t]
    m.addConstrs((PPV[t] + P_imp[t] - P_exp[t] == gp.quicksum(Pc[v, t] 
    for v in range(V))for t in range(N_SLOTS)), name="balance")
    
    
    # 5. Maximum exported electricity
    

    # ── Objective — cost in [€] ───────────────────────────────────────────────
    # [kW] * [€/kWh] * [h] = [€]
    obj = gp.quicksum((P_imp[t] * C_buy[t] - P_exp[t] * C_SELL) * DT for t in range(N_SLOTS))
    
    m.setObjective(obj, GRB.MINIMIZE)

    # ── Solve ─────────────────────────────────────────────────────────────────
    m.Params.DualReductions = 0     # forces Gurobi to distinguish infeasible vs unbounded
    m.optimize()

    # ── Extract results ───────────────────────────────────────────────────────
    if m.Status in [GRB.OPTIMAL, GRB.TIME_LIMIT]:
        slots = np.arange(N_SLOTS)

        results = pd.DataFrame({
            "slot":        slots,
            "t_start":     slots * SLOT_DURATION,
            "P_imp_kW":    [P_imp[t].X for t in slots],
            "P_exp_kW":    [P_exp[t].X for t in slots],
            "PPV_kW":      PPV,
            "total_Pc_kW": [sum(Pc[v, t].X for v in range(V)) for t in slots],
            "C_buy":       C_buy,
        })

        soc_results = pd.DataFrame({
            f"v{v}": [SOC[v, t].X for t in range(N_SLOTS + 1)]
            for v in range(min(V, 20))  # save first 20 vehicles to keep file small
        })

        results.to_parquet(os.path.join(OUTPUT_DIR, "optimization_results.parquet"), index=False)
        soc_results.to_parquet(os.path.join(OUTPUT_DIR, "soc_results.parquet"), index=False)
        
        print(f"Total fleet consumption: {E_cons.sum():.1f} kWh")
        print(f"Total PV available:      {PPV.sum() * DT:.1f} kWh")
        print(f"Total chargeable slots:  {Parked.sum()} vehicle-slots")
        print(f"Avg daily consumption/vehicle: {E_cons.sum() / V:.2f} kWh")


        print(f"\n  → Optimal cost: {m.ObjVal:.2f} €")
        print(f"  → Total import: {results['P_imp_kW'].sum() * DT:.1f} kWh")
        print(f"  → Total export: {results['P_exp_kW'].sum() * DT:.1f} kWh")
        print(f"  → Total PV:     {results['PPV_kW'].sum() * DT:.1f} kWh")

        return results

    else:
        print(f"  ✗ Solver status: {m.Status}")
        return None


if __name__ == "__main__":
    run_optimization()
