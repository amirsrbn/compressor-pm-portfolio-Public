# Simulink Physics Model — Project Roadmap & Test Protocol

**Project:** SGT-400 Gas Turbine Compressor Package — Coupled Dynamic Simulation  
**Methodology:** Agile / Iterative (PMI-ACP aligned)  
**Author:** Amir Sarebanzadeh, PMP®  
**Objective:** Generate physics-grounded time-series dataset for ML pipeline validation

---

## Agile Structure

```
Epic: Physics-Based Simulation Dataset
│
├── Sprint 1 — Gas Turbine Thermodynamic Model      (Week 1)
├── Sprint 2 — Compressor Performance Model         (Week 1-2)
├── Sprint 3 — Degradation & Fault Injection        (Week 2)
├── Sprint 4 — Coupled System Integration           (Week 2-3)
└── Sprint 5 — Dataset Export & ML Pipeline Feed    (Week 3)
```

**Definition of Done (DoD) — applies to every sprint:**
- All outputs within ±5% of design point (Performance Test basis)
- No numerical instability (no NaN, no divergence)
- Unit tests pass (see acceptance criteria per sprint)
- Code committed to GitHub with descriptive commit message

---

## Sprint 1 — Gas Turbine Thermodynamic Model

### Objective
Model the Brayton cycle for the SGT-400 twin-shaft gas turbine.
Output: shaft power delivered to compressor string as function of
ambient conditions, fuel quality, and turbine health.

### Physics
```
Brayton cycle (open, twin-shaft):

  1→2 : Air compression (gas turbine compressor)
        T2 = T1 × (1 + (rp^((γ-1)/γ) - 1) / η_c)
        P2 = P1 × rp

  2→3 : Combustion
        T3 = T2 + Q_fuel × η_comb / (m_air × Cp_gas)
        Q_fuel = m_fuel × LHV_fuel

  3→4 : Gas generator turbine expansion
        T4 = T3 × (1 - η_gg × (1 - (P4/P3)^((γ-1)/γ)))

  4→5 : Power turbine expansion
        T5 = T4 × (1 - η_pt × (1 - (P5/P4)^((γ-1)/γ)))
        W_shaft = m_gas × Cp_gas × (T4 - T5) × η_mech
```

### MATLAB/Simulink Blocks Required
```
1. Ambient conditions input    : T_amb(t), P_amb(t), RH(t)
2. Air intake model            : mass flow = f(T_amb, P_amb, fouling_factor)
3. Combustion model            : T3 = f(AFR, LHV, η_comb)
4. Gas generator turbine       : T4, P4 output
5. Power turbine               : W_shaft output
6. Degradation factors         :
   - η_c degradation (compressor fouling)
   - η_comb degradation (nozzle fouling → EGT spread)
   - η_pt degradation (hot section wear)
```

### Design Point Parameters (SGT-400, Foroozan field)
```
Rated power output      : ~15 MW (site-rated, derated for ambient)
Pressure ratio GT comp  : ~16:1
Turbine inlet temp (T3) : ~1050°C (estimated — OEM proprietary)
Exhaust temperature     : ~480°C (design)
Fuel                    : Associated gas (LHV ≈ 44 MJ/kg) or diesel
Ambient design point    : 35°C, 1.013 bara (Persian Gulf summer)
```

### Time-Varying Inputs (1-year, hourly)
```python
# Ambient temperature — Persian Gulf seasonal + diurnal
T_amb(t) = 35 + 10×sin(2π×t/8760)      # seasonal (summer peak)
          + 8×sin(2π×t/24)               # diurnal
          + N(0, 1.5)                    # measurement noise

# Ambient pressure
P_amb(t) = 1.013 - 0.005×sin(2π×t/8760) + N(0, 0.002)

# Fuel LHV variation (gas composition changes)
LHV(t)   = 44.0 + 2.0×sin(2π×t/2160)   # ~3-month cycle
          + N(0, 0.5)                    # [MJ/kg]

# Nozzle fouling factor (builds up, reset at water wash)
fouling_nozzle(t): piecewise — linear buildup + step reset at wash events
```

### Sprint 1 Acceptance Tests

| Test ID | Description | Pass Criterion |
|---|---|---|
| GT-01 | Design point power output | W_shaft = 13.5–15.5 MW at 35°C |
| GT-02 | Power derate vs temperature | dP/dT = -0.3 to -0.5 %/°C |
| GT-03 | Exhaust temperature range | T_exhaust = 450–510°C |
| GT-04 | EGT spread with nozzle fouling | ΔT_spread increases monotonically with fouling_factor |
| GT-05 | Fuel variation effect | LHV ±5% → W_shaft ±3–5% |
| GT-06 | Numerical stability | No NaN, no oscillation >10% over 8760 steps |
| GT-07 | Annual power profile | Min in summer (high T_amb), max in winter |

### Deliverable
```
simulink/sprint1_gas_turbine/
├── GT_Thermodynamic_Model.m      % MATLAB script (Simulink programmatic)
├── GT_DesignPoint_Validation.m   % Sprint 1 acceptance tests
├── GT_TimeVaryingInputs.m        % 1-year input arrays
└── outputs/
    └── sprint1_shaft_power.csv   % W_shaft(t), T_exhaust(t), EGT_spread(t)
```

---

## Sprint 2 — Compressor Performance Model

### Objective
Model LP and HP centrifugal compressor aerodynamic performance.
Output: discharge conditions, polytropic efficiency, surge margin
as function of shaft speed, inlet conditions, and fouling state.

### Physics
```
Schultz polytropic method (ASME PTC-10):

  Polytropic head:
  H_p = (n_p/(n_p-1)) × Z_mean × R × T_in × [(P_out/P_in)^((n_p-1)/n_p) - 1]

  Polytropic efficiency:
  η_p = H_p / W_specific

  Flow coefficient (similarity):
  φ = Q / (N × D³)

  Head coefficient:
  ψ = H / (N × D)²

  Surge line (quadratic fit to speedlines):
  Q_surge(N) = a0 + a1×N + a2×N²

  Surge margin:
  SM = (Q_actual - Q_surge) / Q_surge × 100 [%]

  Fouling degradation (Tarabrin 1998):
  η_p(t) = η_p0 × (1 - β × (1 - exp(-k×t)))
  Q_surge_effective(t) = Q_surge × (1 + δ_fouling × fouling_factor(t))
```

### Design Points (from Performance Test basis)
```
LP Compressor (STC-SV, 5-stage):
  N_design    = 13,000 rpm
  Q_design    = 8,477 am³/hr
  P_in        = 17.5 bara
  P_out       = 50.5 bara
  T_in        = 28.9°C
  η_p_design  = 81.4%
  PR          = 2.886

HP Compressor (STC-SV, 6-stage):
  N_design    = 13,000 rpm
  Q_design    = 600 am³/hr
  P_in        = 48.8 bara
  P_out       = 129.2 bara
  T_in        = 43.9°C
  η_p_design  = 55.6%
  PR          = 2.648
```

### Time-Varying Inputs
```python
# Gas composition (reservoir aging)
MW(t)   = 21.9 + 1.5×(t/8760) + N(0, 0.3)    # [kg/kmol]
γ(t)    = 1.31 - 0.02×(t/8760)                 # isentropic exponent

# Reservoir pressure decline (Arps exponential)
P_reservoir(t) = P0 × exp(-Di × t)
Di = 0.07/yr   # mature field decline rate

# Compressor fouling (builds up between water washes)
fouling_comp(t): piecewise — Ruth cake model + step reset at wash
```

### Sprint 2 Acceptance Tests

| Test ID | Description | Pass Criterion |
|---|---|---|
| CP-01 | LP design point efficiency | η_p = 81.4% ± 1% at design conditions |
| CP-02 | HP design point efficiency | η_p = 55.6% ± 1% at design conditions |
| CP-03 | Pressure ratio LP | PR = 2.88 ± 0.05 at design point |
| CP-04 | Pressure ratio HP | PR = 2.65 ± 0.05 at design point |
| CP-05 | Surge margin at design | SM = 15–25% (healthy operating band) |
| CP-06 | Fouling effect on efficiency | η_p drops 3–5% over 6 months without wash |
| CP-07 | Speed similarity | Q ∝ N, H ∝ N² — verify at 80%, 93.4%, 105% speed |
| CP-08 | Gas composition sensitivity | MW +10% → η_p change within ±3% |
| CP-09 | Surge line shift with fouling | Q_surge increases with fouling_factor |
| CP-10 | Discharge temperature validity | T_out_LP = 110–125°C at design point |

### Deliverable
```
simulink/sprint2_compressor/
├── LP_Compressor_Model.m
├── HP_Compressor_Model.m
├── Compressor_Validation.m
├── Performance_Map.m              % plots speedlines
└── outputs/
    ├── sprint2_lp_performance.csv
    └── sprint2_hp_performance.csv
```

---

## Sprint 3 — Degradation & Fault Injection

### Objective
Add time-varying degradation modes to the compressor model.
This sprint creates the "fault scenarios" that generate labeled data for ML.

### Degradation Modes Modeled

**Mode 1 — Bearing Wear (vibration progression)**
```
Physical basis: increased bearing clearance → higher dynamic forces

vib_NDE(t) = vib_healthy + A_fault × ((t-t_fault)/(t_alarm-t_fault))^1.8
                                      for t > t_fault

Parameters:
  vib_healthy  = 18 µm (API 670 Zone A)
  A_fault      = 35–50 µm (peak addition before alarm)
  exponent 1.8 = accelerating wear (Hertzian contact fatigue)
```

**Mode 2 — Impeller Fouling (efficiency degradation)**
```
Physical basis: Tarabrin (1998) — blade surface roughness increase

η_p(t) = η_p0 × (1 - β×(1 - exp(-k_fouling × t_since_wash)))
β      = 0.05   (max 5% efficiency loss)
k      = 0.008  (time constant — depends on gas quality)
```

**Mode 3 — Lube Oil Degradation**
```
Physical basis: Ruth (1935) cake filtration + oxidation

ΔP_filter(t) = ΔP0 × (1 + k_cake × √t_since_change)
μ_oil(t)     = μ_fresh × exp(-k_ox × t_since_change)
```

**Mode 4 — Nozzle Fouling (EGT spread)**
```
Physical basis: partial blockage of fuel nozzles → combustion asymmetry

EGT_spread(t) = EGT_spread0 + k_nozzle × fouling_nozzle(t)
T_exhaust_max(t) increases as spread increases
```

**Mode 5 — Seal Gas Degradation**
```
Physical basis: seal face wear → increased primary vent flow

vent_flow(t) = vent_flow_new × (1 + k_seal × t_service_hours)
PDT_primary(t): decreasing trend → maintenance trigger
```

### Fault Scenarios (3 cycles over 3 years)

```
Cycle 1 (Year 1):
  Day 0–280   : healthy baseline
  Day 280–300 : early bearing wear (warning zone)
  Day 300–342 : active fault (fault zone)
  Day 342     : alarm threshold crossed (API 670 Zone C)
  Day 342–348 : forced shutdown + repair
  Day 348–365 : post-repair, fresh baseline

Cycle 2 (Year 2):
  Day 365–620 : healthy baseline
  Day 620–645 : early bearing wear
  Day 645–687 : active fault (higher severity)
  Day 687     : alarm
  Day 687–693 : repair

Cycle 3 (Year 3):
  Day 730–970 : healthy baseline
  Day 970–992 : early bearing wear (lower severity)
  Day 992–1034: active fault
  Day 1034    : alarm
```

### Sprint 3 Acceptance Tests

| Test ID | Description | Pass Criterion |
|---|---|---|
| FT-01 | Bearing vib healthy baseline | vib = 15–22 µm, stable |
| FT-02 | Bearing vib at alarm | vib ≥ 50 µm at day 342 |
| FT-03 | Vibration ramp shape | accelerating (not linear) |
| FT-04 | Fouling efficiency loss | η_p drops 3–5% in 6 months |
| FT-05 | Water wash reset | η_p recovers to within 1% of initial after wash |
| FT-06 | Filter ΔP progression | monotonically increasing between changes |
| FT-07 | EGT spread vs nozzle fouling | positive correlation, R² > 0.85 |
| FT-08 | Fault labels correct | label=0 healthy, 1 warning (14d pre-fault), 2 fault |
| FT-09 | RUL label validity | RUL decreases monotonically to 0 at alarm day |
| FT-10 | 3-cycle consistency | Each cycle physically plausible, different severity |

### Deliverable
```
simulink/sprint3_degradation/
├── Bearing_Wear_Model.m
├── Fouling_Model.m
├── LubeOil_Degradation_Model.m
├── Nozzle_Fouling_Model.m
├── SealGas_Degradation_Model.m
├── Fault_Injection_Controller.m   % orchestrates all fault modes
├── Degradation_Validation.m
└── outputs/
    └── sprint3_degradation_signals.csv
```

---

## Sprint 4 — Coupled System Integration

### Objective
Integrate all sprint 1–3 models into one coupled Simulink system.
Solve interdependencies (e.g. shaft power → compressor speed →
discharge conditions → process demand → speed setpoint).

### Coupling Equations
```
Speed control loop:
  N_setpoint = f(P_discharge_demand, anti-surge margin)
  N_actual   = N_setpoint + ΔN_speed_control_error

Power balance:
  W_available = W_shaft_turbine × η_gearbox
  W_required  = W_compressor_LP + W_compressor_HP
  ΔW = W_available - W_required → N adjustment

Anti-surge control:
  IF SM < 10%: ASV_position increases (recycle opens)
  IF SM < 5% : emergency recycle + alarm

Process demand:
  Q_required(t) = f(reservoir_pressure, injection_well_demand, tidal_effects)
```

### Sprint 4 Acceptance Tests

| Test ID | Description | Pass Criterion |
|---|---|---|
| INT-01 | Power balance closure | ΔW < 1% at steady state |
| INT-02 | Speed controller stability | No oscillation >2% at steady state |
| INT-03 | Anti-surge response | ASV opens when SM < 10% within 2 time steps |
| INT-04 | Reservoir decline effect | P_suction decreases over 3 years by 15–20% |
| INT-05 | Coupled efficiency | η_p degradation propagates to discharge T correctly |
| INT-06 | Full 3-year run | Completes 26,280 steps without divergence |
| INT-07 | Cross-signal correlation | vib and bearing_T correlated during fault (R²>0.7) |
| INT-08 | Process-mechanical coupling | Low gas flow → lower shaft speed → lower vib |

### Deliverable
```
simulink/sprint4_integration/
├── SGT400_Coupled_Model.m         % master Simulink model
├── SpeedController.m
├── AntiSurge_Controller.m
├── ProcessDemand_Model.m
├── Integration_Tests.m
└── outputs/
    └── sprint4_integrated_signals.csv  % all 14 signals, 26,280 rows
```

---

## Sprint 5 — Dataset Export & ML Pipeline Feed

### Objective
Export final Simulink output as clean dataset compatible with
the existing Python ML pipeline (anomaly_detection.py, rul_lstm.py,
surge_model.py).

### Output Format
```python
# Final dataset schema — matches ML pipeline FEATURES list
columns = [
    "timestamp",              # datetime, hourly
    "vib_NDE_X_um",          # bearing vibration
    "vib_NDE_Y_um",
    "vib_DE_X_um",
    "vib_DE_Y_um",
    "axial_disp_A_mm",
    "axial_disp_B_mm",
    "bearing_NDE_T_C",
    "bearing_DE_T_C",
    "poly_eta_realtime_pct",  # computed from P, T
    "discharge_T_C",
    "inlet_P_bara",
    "lube_P_bara",
    "lube_filter_dP_bar",
    "seal_gas_LP_dP_bar",
    "fault_label",            # 0=healthy, 1=warning, 2=fault
    "rul_days",               # days to next alarm event
    # Additional Simulink-only signals (bonus for analysis):
    "shaft_power_kW",
    "surge_margin_pct",
    "EGT_spread_C",
    "ASV_position_pct",
    "lube_oil_viscosity",
    "gas_MW",
    "T_ambient_C",
]
```

### Sprint 5 Acceptance Tests

| Test ID | Description | Pass Criterion |
|---|---|---|
| EX-01 | Row count | 26,280 rows (3 years × 8760 hr) |
| EX-02 | No missing values | 0 NaN in any column |
| EX-03 | Signal ranges physical | All values within engineering limits |
| EX-04 | Fault label distribution | label=2: 10–20% of dataset |
| EX-05 | RUL label continuity | No discontinuities except at repair events |
| EX-06 | ML pipeline import | anomaly_detection.py runs without error on new data |
| EX-07 | Anomaly model improvement | ROC-AUC ≥ 0.85 on Simulink data (vs 0.831 synthetic) |
| EX-08 | RUL model improvement | MAE ≤ 7.0 days on Simulink data (vs 7.6 synthetic) |
| EX-09 | Parquet export | lp_simulink.parquet readable by pandas |
| EX-10 | Fleet generator compatible | fleet_generator.py accepts new dataset as base |

### Deliverable
```
simulink/sprint5_export/
├── Export_Dataset.m               % MATLAB export script
├── Validate_Export.py             % Python validation script
├── Compare_Synthetic_vs_Simulink.py  % before/after ML comparison
└── outputs/
    ├── lp_simulink.parquet        % final dataset — replaces lp_multiyear.parquet
    └── simulink_vs_synthetic_comparison.png
```

---

## Overall Acceptance Criteria

Before replacing the synthetic dataset with the Simulink dataset:

| Criterion | Requirement |
|---|---|
| Design point match | All key parameters within ±5% of Performance Test basis |
| 3-year stability | No numerical divergence over full simulation |
| Fault label accuracy | Fault events match injected fault schedule exactly |
| ML improvement | At least one model shows improved metrics vs synthetic |
| Peer review | Engineering logic reviewed and signed off by domain expert |

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Numerical instability in coupled model | Medium | High | Use variable-step solver (ode45), add damping |
| Design point mismatch >5% | Low | Medium | Calibrate against Performance Test data |
| Simulink license unavailable | Low | High | Fall back to Python physics model (same equations) |
| Real operational data arrives before completion | Medium | Low | Pause Simulink, use real data directly |

---

## Tooling

```
MATLAB R2021b or later (Student/Professional)
  Required toolboxes:
  - Simulink
  - Simscape (for physical modeling)
  - Control System Toolbox (for speed controller)

Python 3.10+ (for export validation)
  - pandas, numpy, pyarrow, scikit-learn, torch
```

---

## GitHub Commit Convention

```
feat(sim-sprint1): gas turbine thermodynamic model
feat(sim-sprint2): LP/HP compressor performance model
feat(sim-sprint3): degradation and fault injection
feat(sim-sprint4): coupled system integration
feat(sim-sprint5): dataset export and ML pipeline feed
test(sim-sprint1): GT acceptance tests — all pass
fix(sim-sprint2): correct polytropic exponent for HP gas
```

---

*This roadmap follows PMI-ACP Agile principles:*
*iterative delivery, working software over documentation,*
*acceptance-test-driven development, continuous integration.*
