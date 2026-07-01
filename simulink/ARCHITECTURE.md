# Simulink Model Architecture — SGT-400 Compressor Package

**Project:** SGT-400 Gas Turbine Compressor Package — Coupled Dynamic Simulation  
**Author:** Amir Sarebanzadeh, PMP  
**Last Updated:** 2026-06-28  
**Branch:** `claude/wonderful-mayer-ww8pci`

---

## Design Principle

The simulation is divided into **6 strictly separated layers**.
Each layer has one responsibility and defined input/output contracts.
No layer may call a layer above itself.
Layers 1–3 must produce **deterministic outputs** for a given random seed —
stochastic noise is isolated to Layer 4 only.

```
┌─────────────────────────────────────────────────────┐
│  Layer 6 — Dataset Exporter          [Sprint 5] ✅  │
├─────────────────────────────────────────────────────┤
│  Layer 5 — Coupled System Integrator [Sprint 4] ✅  │
├─────────────────────────────────────────────────────┤
│  Layer 4 — Sensor Noise Layer        [Sprint 5] ✅  │
├─────────────────────────────────────┬───────────────┤
│  Layer 3 — Fault / Degradation      │               │
├─────────────────────────────────────┤  Layer 2      │
│  Layer 1 — Compressor Core Model    │  Disturbance  │
└─────────────────────────────────────┴───────────────┘
```

---

## Model Block Diagram

```
╔══════════════════════════════════════════════════════════════════════════╗
║                    SGT-400 Coupled Simulation                            ║
║                  SGT400_CoupledModel.m (Layer 5)                         ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  ┌─────────────────────────────────────────────────────────────────┐    ║
║  │ LAYER 2 — Disturbances                                          │    ║
║  │                                                                 │    ║
║  │  Reservoir_PressureDecline ──► P_res(t)                         │    ║
║  │  Process_Demand_Model      ──► Q_demand(t), N_setpoint(t)       │    ║
║  └────────────────────────────────┬────────────────────────────────┘    ║
║                                   │                                      ║
║                                   ▼                                      ║
║  ┌─────────────────────────────────────────────────────────────────┐    ║
║  │ LAYER 3 — Degradation / Faults                                  │    ║
║  │                                                                 │    ║
║  │  Compressor_Fouling    ──► fouling_lp(t), fouling_hp(t)         │    ║
║  │                            eta_p_LP_fouled(t)                   │    ║
║  │  Bearing_Wear_Model    ──► vib_NDE_X_smooth(t)                  │    ║
║  │  LubeOil_Degradation   ──► lube_filter_dP(t), lube_T(t)         │    ║
║  │  SealGas_Degradation   ──► seal_gas_LP_dP(t)                    │    ║
║  │  Nozzle_Fouling_EGT    ──► EGT_spread(t), fouling_nozzle(t)     │    ║
║  │  Fault_Label_Generator ──► fault_label(t), RUL(t)               │    ║
║  └────────────────────────────────┬────────────────────────────────┘    ║
║                                   │                                      ║
║                                   ▼                                      ║
║  ┌─────────────────────────────────────────────────────────────────┐    ║
║  │ LAYER 1 — Core Physics (per time step)                          │    ║
║  │                                                                 │    ║
║  │  LP_Compressor_Model ──► W_LP(t), SM_LP(t), PR_LP(t)           │    ║
║  │  HP_Compressor_Model ──► W_HP(t), SM_HP(t), PR_HP(t)           │    ║
║  │  GT_BraytonCycle     ──► W_shaft_GT(t), T_exhaust(t)            │    ║
║  └────────────────────────────────┬────────────────────────────────┘    ║
║                                   │                                      ║
║                                   ▼                                      ║
║  ┌─────────────────────────────────────────────────────────────────┐    ║
║  │ LAYER 5 — Coupled Integration Loop (26,280 steps)               │    ║
║  │                                                                 │    ║
║  │  ╔══════════════════════════════════════════════════╗           │    ║
║  │  ║  for h = 1 : 26280                               ║           │    ║
║  │  ║                                                  ║           │    ║
║  │  ║  [1] Scale W_LP, W_HP with N^3 (affinity law)   ║           │    ║
║  │  ║  [2] Power_Balance_Solver                        ║           │    ║
║  │  ║      W_avail = W_shaft_GT × η_gb                ║           │    ║
║  │  ║      W_req   = W_LP + W_HP                      ║           │    ║
║  │  ║      iterate until |ΔW/W_req| < 1%  (≤5 iter)   ║           │    ║
║  │  ║  [3] Speed_Controller (PI, Kp=0.5, Ki=0.1)      ║           │    ║
║  │  ║      N ← N + Kp·e + Ki·∫e dt                   ║           │    ║
║  │  ║      anti-windup: freeze integrator at limits   ║           │    ║
║  │  ║  [4] Gearbox_Model                              ║           │    ║
║  │  ║      W_output = W_input × 0.985                 ║           │    ║
║  │  ║      6 RTD bearing temperatures                 ║           │    ║
║  │  ║  [5] Inline anti-surge (ASV + recycle)          ║           │    ║
║  │  ╚══════════════════════════════════════════════════╝           │    ║
║  └────────────────────────────────┬────────────────────────────────┘    ║
║                                   │                                      ║
║                                   ▼                                      ║
║  ┌─────────────────────────────────────────────────────────────────┐    ║
║  │ LAYER 4 — Sensor Noise Layer            [Sprint 5] ✅           │    ║
║  │  Sensor_Noise_Layer.m                                           │    ║
║  │  signal_measured = signal_true + bias + randn()·σ               │    ║
║  │  Instruments: PT 0.005 bara | TT 0.5°C+drift | FT 0.3%FS       │    ║
║  │               VT 1.2 µm | ST 2 rpm | WT 0.5%FS                  │    ║
║  └────────────────────────────────┬────────────────────────────────┘    ║
║                                   │                                      ║
║                                   ▼                                      ║
║  ┌─────────────────────────────────────────────────────────────────┐    ║
║  │ LAYER 6 — Dataset Exporter              [Sprint 5] ✅           │    ║
║  │  Export_Dataset.m ──► lp_simulink_raw.csv, lp_simulink.parquet  │    ║
║  │  26,280 rows × 18 columns | timestamp 2023-01-01T00:00Z + 1h    │    ║
║  └─────────────────────────────────────────────────────────────────┘    ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## Sprint Status

| Sprint | Scope | Status |
|--------|-------|--------|
| Sprint 1 | GT Brayton cycle, time-varying inputs | ✅ Complete |
| Sprint 2 | LP/HP compressors, reservoir, anti-surge, validation | ✅ Complete |
| Sprint 3 | Bearing wear, lube oil, seal gas, nozzle fouling, fault labels, validation | ✅ Complete |
| Sprint 4 | Coupled integration: power balance, speed controller, demand model, gearbox | ✅ Complete |
| Sprint 5 | Sensor noise (Layer 4), dataset export (Layer 6), TD-001 fix | ✅ Complete |

---

## Layer 1 — Compressor Core Model

**Responsibility:** Pure physics. Given operating point inputs, compute
thermodynamic outputs using Schultz polytropic method (ASME PTC-10).
No randomness. No degradation. No fault injection.

**Files:**
- `sprint2_compressor/LP_Compressor_Model.m`
- `sprint2_compressor/HP_Compressor_Model.m`

**Inputs (all clean, no noise):**

| Signal | Unit | Source |
|--------|------|--------|
| `N_shaft` | rpm | Layer 5 (speed controller) |
| `P_in` | bara | Layer 2 (reservoir) or Layer 5 |
| `T_in` | °C | Layer 2 (gas composition) |
| `MW_gas` | kg/kmol | Layer 2 |
| `gamma` | — | Layer 2 |
| `Z` | — | Layer 2 |
| `Q_demand` | am³/hr | Layer 5 (process demand) |
| `fouling_lp` / `fouling_hp` | — | Layer 3 (passed in as parameter) |

**Outputs:**

| Signal | Unit | Description |
|--------|------|-------------|
| `H_p` | kJ/kg | Polytropic head |
| `eta_p` | — | Polytropic efficiency (clean × fouling factor) |
| `PR` | — | Pressure ratio |
| `T_out` | °C | Discharge temperature |
| `W_shaft` | kW | Shaft power consumed |
| `SM` | % | Surge margin |
| `Q_surge` | am³/hr | Surge flow at current N |

**Rules — MUST NOT contain:**
- `randn()`, `rand()`, or any stochastic call ← **TD-001 FIXED Sprint 5**
- Fault injection logic
- Direct fouling buildup calculation (receives `fouling_lp` from Layer 3)

---

## Layer 2 — Disturbance Generator

**Responsibility:** Generate time-varying boundary condition arrays
for 8,760 (1-year) or 26,280 (3-year) hourly steps.
Represents the operating environment, not equipment health.

**Files:**
- `sprint1_gas_turbine/GT_TimeVaryingInputs.m`
- `sprint2_compressor/Compressor_GasProperties.m`
- `sprint2_compressor/Reservoir_PressureDecline.m`
- `sprint4_integration/Process_Demand_Model.m`

**Outputs:**

| Signal | Unit | File |
|--------|------|------|
| `T_amb` | °C | `ambient_inputs.mat` |
| `P_amb` | bara | `ambient_inputs.mat` |
| `RH` | % | `ambient_inputs.mat` |
| `LHV` | MJ/kg | `fuel_inputs.mat` |
| `MW_fuel` | kg/kmol | `fuel_inputs.mat` |
| `WI` | — | `fuel_inputs.mat` |
| `MW_gas` | kg/kmol | `gas_composition.mat` |
| `gamma_gas` | — | `gas_composition.mat` |
| `Z_LP`, `Z_HP` | — | `gas_composition.mat` |
| `P_reservoir` | bara | `reservoir_decline.mat` |
| `Q_demand` | am³/hr | `process_demand.mat` |
| `N_setpoint` | rpm | `process_demand.mat` |

---

## Layer 3 — Fault / Degradation Generator

**Responsibility:** Generate equipment health signals over time.
Produces degradation factors and fault indicators.
Outputs are the **true physical state** — not yet corrupted by sensor noise.

**Files:**

| File | Description |
|------|-------------|
| `sprint1_gas_turbine/GT_Degradation.m` | GT hot section wear, GT compressor fouling |
| `sprint2_compressor/Compressor_Fouling.m` | LP/HP fouling factors, surge line shift |
| `sprint3_degradation/Bearing_Wear_Model.m` | Weibull ramp, 3 fault cycles, API 670 |
| `sprint3_degradation/LubeOil_Degradation.m` | Ruth cake filtration, oil temp rise |
| `sprint3_degradation/SealGas_Degradation.m` | Seal face wear, supply dips |
| `sprint3_degradation/Nozzle_Fouling_EGT.m` | Nozzle fouling, EGT spread |
| `sprint3_degradation/Fault_Label_Generator.m` | Ground truth labels and RUL |

**Outputs:**

| Signal | Unit | Description |
|--------|------|-------------|
| `fouling_lp` | — | LP compressor fouling factor [0,1] |
| `fouling_hp` | — | HP compressor fouling factor [0,1] |
| `eta_p_LP_fouled` | — | LP efficiency with fouling applied |
| `eta_p_HP_fouled` | — | HP efficiency with fouling applied |
| `Q_surge_LP_eff` | am³/hr | Surge flow with fouling shift |
| `vib_NDE_X` | µm | True bearing vibration (X plane) |
| `vib_NDE_X_smooth` | µm | 24h MA — used for API 670 alarm logic |
| `bearing_NDE_T` | °C | True bearing temperature |
| `axial_disp` | mm | Rotor axial displacement |
| `lube_filter_dP` | bar | Filter differential pressure |
| `lube_P` | bara | Lube oil supply pressure |
| `lube_T` | °C | Lube oil temperature |
| `seal_gas_LP_dP` | bar | Seal gas differential pressure |
| `fouling_nozzle` | — | Combustor nozzle fouling factor |
| `EGT_spread` | °C | Exhaust gas temperature spread |
| `fault_label` | 0/1/2 | Ground truth fault label |
| `RUL` | h | Remaining useful life [0, 1440h] |

---

## Layer 4 — Sensor Noise Layer

**STATUS: ✅ Implemented (Sprint 5)**

**File:** `sprint5_export/Sensor_Noise_Layer.m`

**Responsibility:** Add instrument-specific noise to every signal before
it reaches the ML dataset. This is the only layer where sensor
characteristics (accuracy, drift, quantisation) are modelled.

**Noise parameters (ISA 5.1 / API 670):**

| Instrument | σ | Drift | Model |
|------------|---|-------|-------|
| PT (pressure) | 0.005 bara | none | smart transmitter |
| TT (temperature) | 0.5 °C | +1 °C / 3yr linear | RTD Class B |
| FT (flow) | 0.3% FS = 25.4 am³/hr | none | ultrasonic/Coriolis |
| VT (vibration) | 1.2 µm | none | API 670 proximity |
| ST (speed) | 2 rpm | none | magnetic pickup |
| WT (power) | 0.5% FS = 39.75 kW | none | power meter |

**Output:** `sgt400_measured.mat` — all `*_meas` signals

---

## Layer 5 — Coupled System Integrator

**STATUS: ✅ Implemented (Sprint 4)**

**Files:**

| File | Responsibility |
|------|----------------|
| `sprint4_integration/SGT400_CoupledModel.m` | Master coupled integration loop |
| `sprint4_integration/Power_Balance_Solver.m` | Newton iteration for shaft power balance |
| `sprint4_integration/Speed_Controller.m` | Discrete PI governor with anti-windup |
| `sprint4_integration/Process_Demand_Model.m` | Q demand profile (Layer 2 boundary) |
| `sprint4_integration/Gearbox_Model.m` | Mechanical transmission η=0.985, 6 RTDs |

**Integration tests:**

| Test | Criterion | Result |
|------|-----------|--------|
| INT-01 | Power balance ≤ 5 iterations at every step | ✅ |
| INT-02 | N_balanced ∈ [9000, 14500] rpm always | ✅ |
| INT-03 | Post-antisurge surge margin > 0 throughout | ✅ |
| INT-04 | \|ΔW/W_req\| < 1% at convergence | ✅ |
| INT-05 | EGT spread ≤ 50°C always | ✅ |
| INT-06 | 3 bearing fault cycles detected | ✅ |
| INT-07 | RUL=0 at alarm hour, resets after repair | ✅ |
| INT-08 | corr(Q_demand, P_res) < −0.5 | ✅ |

---

## Layer 6 — Dataset Exporter

**STATUS: ✅ Implemented (Sprint 5)**

**File:** `sprint5_export/Export_Dataset.m`

**Output schema (18 columns, 26,280 rows):**

| Column | Unit | Source |
|--------|------|--------|
| `timestamp` | datetime | 2023-01-01T00:00Z + 1h/row |
| `N_meas` | rpm | L4 ST |
| `Q_meas` | am³/hr | L4 FT |
| `W_shaft_meas` | W | L4 WT |
| `vib_NDE_X_meas` | µm | L4 VT |
| `bearing_T_meas` | °C | L4 TT (RTD-1) |
| `lube_T_meas` | °C | L4 TT |
| `lube_P_meas` | bara | L4 PT |
| `lube_filter_dP_meas` | bar | L4 PT |
| `seal_dP_LP_meas` | bar | L4 PT |
| `seal_dP_HP_meas` | bar | L4 PT |
| `EGT_spread_meas` | °C | L4 TT |
| `SM_LP_meas` | % | L4 derived |
| `SM_HP_meas` | % | L4 derived |
| `PR_LP_meas` | — | L4 derived (2×PT) |
| `T_out_LP_meas` | °C | L4 TT |
| `fault_label` | int32 | L3 ground truth |
| `RUL` | h | L3 ground truth |

**Output files:** `lp_simulink_raw.csv` (~3 MB), `lp_simulink.parquet` (~0.5 MB, R2019b+)

---

## Technical Debt Register

### TD-001 — `randn()` inside Layer 1 ✅ FIXED (Sprint 5)

**Location:** `sprint2_compressor/LP_Compressor_Model.m`  
**Fix:** Replaced `randn()` in N_shaft calculation with deterministic
`sin(2π·t/168 + 1.3)` (weekly governor ripple). Layer 1 is now fully
deterministic. Stochastic calls live exclusively in Layer 4.

### TD-002 — Fouling correction inside Layer 1 ✅ FIXED (Sprint 4)

**Sprint 4 fix:** `SGT400_CoupledModel.m` passes `eta_p_LP_fouled`
(from Layer 3) directly to the power scaling equation.
Layer 1 physics no longer re-applies fouling. Double-application eliminated.

### TD-003 — File naming inconsistency ✅ DOCUMENTED

**Files:** `LubeOil_Degradation.m`, `SealGas_Degradation.m`, `Nozzle_Fouling_EGT.m`  
**Mitigation:** `SGT400_CoupledModel.m` uses a filename-agnostic
`for cand` loop that accepts all known name variants. Rename deferred.

---

## Signal Flow Diagram

```
Layer 2 (Disturbances)
  Reservoir_PressureDecline ──► P_res(t)
  Process_Demand_Model      ──► Q_demand(t), N_setpoint(t)
        │
        ▼
Layer 3 (Degradation)
  Compressor_Fouling    ──► fouling_lp(t), eta_p_LP_fouled(t)
  Bearing_Wear_Model    ──► vib_NDE_X_smooth(t)
  LubeOil_Degradation   ──► lube_filter_dP(t), lube_T(t)
  SealGas_Degradation   ──► seal_gas_LP_dP(t)
  Nozzle_Fouling_EGT    ──► EGT_spread(t), fouling_nozzle(t)
  Fault_Label_Generator ──► fault_label(t), RUL(t)
        │
        ▼
Layer 1 (Core Physics — per step)
  LP_Compressor_Model ──► W_LP(t), SM_LP(t), PR_LP(t)
  HP_Compressor_Model ──► W_HP(t), SM_HP(t), PR_HP(t)
  GT_BraytonCycle     ──► W_shaft_GT(t), T_exhaust(t)
        │
        ▼
Layer 5 (Integration loop — 26,280 steps)
  Power_Balance_Solver ──► N_balanced(t), converged(t), iter_count(t)
  Speed_Controller     ──► N(t+1), integrator state
  Gearbox_Model        ──► W_output(t), T_bearing_RTD(t)
  [Inline anti-surge]  ──► ASV_LP(t), Q_recycle(t), SM_LP_AS(t)
        │
        ▼
Layer 4 (Sensor Noise — Sprint 5) ✅
  Sensor_Noise_Layer   ──► *_meas signals → sgt400_measured.mat
        │
        ▼
Layer 6 (Export — Sprint 5) ✅
  Export_Dataset       ──► lp_simulink_raw.csv, lp_simulink.parquet
```

---

## Dependency Matrix

| File | Reads from | Writes to |
|------|-----------|----------|
| `GT_TimeVaryingInputs.m` | — | `ambient_inputs.mat`, `fuel_inputs.mat` |
| `Compressor_GasProperties.m` | — | `gas_composition.mat` |
| `Reservoir_PressureDecline.m` | — | `reservoir_decline.mat` |
| `Process_Demand_Model.m` | `reservoir_decline.mat` | `process_demand.mat` |
| `GT_Degradation.m` | `ambient_inputs.mat` | `gt_degradation.mat` |
| `Compressor_Fouling.m` | `lp_performance.mat`, `hp_performance.mat` | `fouling_model.mat` |
| `Bearing_Wear_Model.m` | — | `bearing_wear.mat` |
| `LubeOil_Degradation.m` | — | `lube_oil.mat` |
| `SealGas_Degradation.m` | — | `seal_gas.mat` |
| `Nozzle_Fouling_EGT.m` | — | `nozzle_fouling.mat` |
| `Fault_Label_Generator.m` | `bearing_wear.mat` | `fault_labels.mat` |
| `LP_Compressor_Model.m` | `gas_composition.mat` | `lp_performance.mat` |
| `HP_Compressor_Model.m` | `gas_composition.mat`, `lp_performance.mat` | `hp_performance.mat` |
| `GT_BraytonCycle.m` | `ambient_inputs.mat`, `fuel_inputs.mat`, `gt_degradation.mat` | `gt_performance.mat` |
| `AntiSurge_Controller.m` | `lp_performance.mat`, `hp_performance.mat` | `antisurge_control.mat` |
| `Gearbox_Model.m` | `gt_model.mat` *(opt)*, `lube_oil.mat` *(opt)* | `gearbox_model.mat` |
| `SGT400_CoupledModel.m` | all `.mat` files above | `sgt400_coupled.mat` |
| `Sensor_Noise_Layer.m` | `sgt400_coupled.mat` + optional sub-mats | `sgt400_measured.mat` |
| `Export_Dataset.m` | `sgt400_measured.mat` | `lp_simulink_raw.csv`, `lp_simulink.parquet` |
