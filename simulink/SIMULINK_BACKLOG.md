# Simulink Physics Model — Product Backlog

**Project:** SGT-400 Gas Turbine Compressor Package — Coupled Dynamic Simulation  
**Product Owner:** Amir Sarebanzadeh, PMP®  
**Methodology:** Agile / Scrum (PMI-ACP aligned)  
**Last Updated:** 2026-06-28  
**Status:** Backlog Groomed — Ready for Sprint 1

---

## Backlog Structure

```
Priority: P1 (Must Have) → P2 (Should Have) → P3 (Nice to Have)
Story Points: 1 (trivial) → 3 (small) → 5 (medium) → 8 (large) → 13 (epic)
Status: 📋 Backlog | 🔄 In Progress | ✅ Done | ❌ Blocked
```

---

## EPIC 1 — Gas Turbine Thermodynamic Model
**Sprint 1 | Total Story Points: 34**

---

### US-001 — Ambient Conditions Input Array
**Priority:** P1 | **Points:** 3 | **Status:** 📋 Backlog

**User Story:**
As a simulation engineer, I want a time-varying ambient conditions
array (T, P, RH) for 8,760 hourly steps so that the gas turbine
model reflects real Persian Gulf seasonal and diurnal variation.

**Acceptance Criteria:**
- [ ] T_ambient: mean 35°C, seasonal ±10°C, diurnal ±8°C, noise σ=1.5°C
- [ ] P_ambient: mean 1.013 bara, seasonal ±0.005 bara
- [ ] RH: mean 70%, seasonal variation ±20%
- [ ] Output: MATLAB array [8760×3], saved as `ambient_inputs.mat`
- [ ] Plot: annual temperature profile — visually shows summer peak

**Technical Notes:**
```matlab
t = 0:8759;  % hourly steps
T_amb = 35 + 10*sin(2*pi*t/8760) + 8*sin(2*pi*t/24) + randn(size(t))*1.5;
```

---

### US-002 — Fuel Quality Time Series
**Priority:** P1 | **Points:** 3 | **Status:** 📋 Backlog

**User Story:**
As a simulation engineer, I want a time-varying fuel quality array
(LHV, Wobbe Index, gas composition) so that combustion model
reflects real field gas composition changes.

**Acceptance Criteria:**
- [ ] LHV: mean 44 MJ/kg, ±2 MJ/kg seasonal variation, noise σ=0.5
- [ ] Wobbe Index: derived from LHV and gas density
- [ ] MW_fuel: mean 20 kg/kmol, slow drift +1.5 kg/kmol/year
- [ ] Output: `fuel_inputs.mat` [8760×3]
- [ ] Correlation: MW_fuel and LHV negatively correlated (heavier gas = lower LHV)

---

### US-003 — Air Intake Mass Flow Model
**Priority:** P1 | **Points:** 5 | **Status:** 📋 Backlog

**User Story:**
As a simulation engineer, I want an air mass flow model that
accounts for ambient density and inlet filter fouling so that
turbine performance degradation due to air restriction is captured.

**Acceptance Criteria:**
- [ ] m_air = f(T_amb, P_amb, fouling_filter_factor)
- [ ] Design point: m_air at 35°C/1.013 bara within ±2% of OEM spec
- [ ] Fouling effect: 5% flow reduction at max filter ΔP (0.5 mbar)
- [ ] Filter ΔP modeled with Ruth cake filtration
- [ ] Output: m_air(t) array [8760×1]

---

### US-004 — Combustion Chamber Model
**Priority:** P1 | **Points:** 8 | **Status:** 📋 Backlog

**User Story:**
As a simulation engineer, I want a combustion model that computes
turbine inlet temperature (T3) and accounts for nozzle fouling
(EGT spread) so that hot section degradation is captured.

**Acceptance Criteria:**
- [ ] T3 = f(T2, AFR, LHV, η_comb, nozzle_fouling_factor)
- [ ] T3 at design: 1,050°C ± 30°C (estimated OEM range)
- [ ] η_comb_design = 0.995 (typical gas turbine)
- [ ] EGT_spread_healthy: < 15°C
- [ ] EGT_spread_fouled: up to 50°C at max fouling
- [ ] Nozzle fouling factor: piecewise buildup + step reset at combustor wash
- [ ] Output: T3(t), EGT_spread(t) [8760×1 each]

**Sub-tasks:**
- [ ] Define nozzle_fouling_factor(t) — 3 wash events in 3 years
- [ ] Validate EGT spread vs published SGT-400 field data (literature)

---

### US-005 — Gas Generator Turbine Model
**Priority:** P1 | **Points:** 5 | **Status:** 📋 Backlog

**User Story:**
As a simulation engineer, I want a gas generator turbine expansion
model that computes conditions at power turbine inlet (T4, P4)
so that power turbine model has correct boundary conditions.

**Acceptance Criteria:**
- [ ] T4 = T3 × (1 - η_gg × (1 - (P4/P3)^((γ-1)/γ)))
- [ ] η_gg_design = 0.87 (typical)
- [ ] P4/P3 split ratio: 60/40 (gas gen / power turbine) ± tuning
- [ ] T4 at design: 780–850°C range
- [ ] Hot section degradation: η_gg drops 0.5–1% per 8,000 hr

---

### US-006 — Power Turbine & Shaft Power Model
**Priority:** P1 | **Points:** 5 | **Status:** 📋 Backlog

**User Story:**
As a simulation engineer, I want a power turbine model that
computes shaft power output (W_shaft) as function of T4, P4,
and turbine health so that compressor model has correct driver power.

**Acceptance Criteria:**
- [ ] W_shaft = m_gas × Cp_gas × (T4-T5) × η_pt × η_mech
- [ ] W_shaft at design (35°C): 13.5–15.5 MW range
- [ ] Power derate vs T_amb: -0.3 to -0.5 %/°C — verify GT-02
- [ ] Exhaust T5: 450–510°C at design
- [ ] Output: W_shaft(t), T_exhaust(t) [8760×1 each]

---

### US-007 — Sprint 1 Integration & Validation
**Priority:** P1 | **Points:** 5 | **Status:** 📋 Backlog

**User Story:**
As a simulation engineer, I want all Sprint 1 components integrated
and all 7 acceptance tests passing so that Sprint 1 is complete
per Definition of Done.

**Acceptance Criteria:**
- [ ] GT-01 through GT-07 all pass (see SIMULINK_ROADMAP.md)
- [ ] `sprint1_shaft_power.csv` exported: W_shaft(t), T_exhaust(t), EGT_spread(t)
- [ ] Annual power profile plot: min in summer, max in winter
- [ ] Commit: `feat(sim-sprint1): gas turbine thermodynamic model`

---

## EPIC 2 — Compressor Performance Model
**Sprint 2 | Total Story Points: 42**

---

### US-008 — Gas Composition Time Series
**Priority:** P1 | **Points:** 3 | **Status:** 📋 Backlog

**User Story:**
As a simulation engineer, I want a time-varying gas composition
array (MW, γ, Z) for 8,760 steps so that compressor thermodynamic
calculations reflect reservoir aging.

**Acceptance Criteria:**
- [ ] MW: 21.9 → 23.4 kg/kmol over 3 years (reservoir aging)
- [ ] γ: 1.31 → 1.29 (heavier gas = lower γ)
- [ ] Z_inlet: computed from BWRS EOS at each time step
- [ ] MW and γ negatively correlated
- [ ] Output: `gas_composition.mat` [8760×3]

---

### US-009 — LP Compressor Performance Map
**Priority:** P1 | **Points:** 8 | **Status:** 📋 Backlog

**User Story:**
As a simulation engineer, I want an LP compressor model based on
Schultz polytropic method and similarity laws so that discharge
conditions and efficiency are computed correctly at any operating point.

**Acceptance Criteria:**
- [ ] η_p at design: 81.4% ± 1%
- [ ] PR at design: 2.886 ± 0.05
- [ ] T_discharge at design: 116°C ± 3°C
- [ ] Speedlines at 80%, 93.4%, 105% speed — verify similarity laws
- [ ] Surge line: Q_surge(N) = a0 + a1×N + a2×N²
- [ ] Surge margin at design: 15–25%
- [ ] Output: performance map plot + `lp_performance.mat`

**Sub-tasks:**
- [ ] Implement Schultz polytropic head equation
- [ ] Fit surge line quadratic coefficients to 3 speedline points
- [ ] Implement flow coefficient φ and head coefficient ψ
- [ ] Validate similarity: Q∝N, H∝N² at constant density

---

### US-010 — HP Compressor Performance Map
**Priority:** P1 | **Points:** 8 | **Status:** 📋 Backlog

**User Story:**
As a simulation engineer, I want an HP compressor model with the
same Schultz methodology so that HP discharge conditions feed
correctly into the process model.

**Acceptance Criteria:**
- [ ] η_p at design: 55.6% ± 1%
- [ ] PR at design: 2.648 ± 0.05
- [ ] T_discharge at design: 162°C ± 4°C
- [ ] Surge margin at design: 15–25%
- [ ] Note: HP has lower η_p due to higher pressure ratio and smaller flow coefficient
- [ ] Output: HP performance map plot + `hp_performance.mat`

---

### US-011 — Compressor Fouling Model
**Priority:** P1 | **Points:** 5 | **Status:** 📋 Backlog

**User Story:**
As a simulation engineer, I want a fouling degradation model
(Tarabrin 1998) applied to both LP and HP so that efficiency
loss and surge line shift are captured over time.

**Acceptance Criteria:**
- [ ] η_p(t) = η_p0 × (1 - β×(1-exp(-k×t_since_wash)))
- [ ] β = 0.05 (5% max efficiency loss)
- [ ] k = 0.008 (time constant)
- [ ] 3 water wash events in 3 years — η_p recovers within 1% of initial
- [ ] Surge line shifts inward by up to 5% at max fouling
- [ ] Output: fouling_factor(t), η_p_actual(t) [8760×1 each]

---

### US-012 — Reservoir Pressure Decline Model
**Priority:** P1 | **Points:** 5 | **Status:** 📋 Backlog

**User Story:**
As a simulation engineer, I want an Arps exponential decline model
for reservoir pressure so that compressor inlet conditions reflect
real field depletion over 3 years.

**Acceptance Criteria:**
- [ ] P_reservoir(t) = P0 × exp(-Di × t_years)
- [ ] P0 = 17.5 bara (LP suction design)
- [ ] Di = 0.07/year (mature field, Foroozan basis)
- [ ] P_reservoir at year 3: ~14.2 bara (18.7% decline)
- [ ] Add noise: σ = 0.05 bara
- [ ] Output: P_suction_LP(t), P_suction_HP(t) [8760×1 each]

---

### US-013 — Anti-Surge Control Model
**Priority:** P1 | **Points:** 5 | **Status:** 📋 Backlog

**User Story:**
As a simulation engineer, I want an anti-surge controller model
that opens the recycle valve when surge margin drops below 10%
so that surge approach events are captured in the dataset.

**Acceptance Criteria:**
- [ ] SM = (Q_actual - Q_surge_effective) / Q_surge_effective × 100
- [ ] ASV_position = 0% when SM > 15%
- [ ] ASV_position ramps open when SM < 10% (proportional control)
- [ ] Emergency recycle when SM < 5%
- [ ] 6 surge approach events injected over 3 years
- [ ] Output: SM(t), ASV_position(t) [8760×1 each]

---

### US-014 — Sprint 2 Integration & Validation
**Priority:** P1 | **Points:** 8 | **Status:** 📋 Backlog

**Acceptance Criteria:**
- [ ] CP-01 through CP-10 all pass (see SIMULINK_ROADMAP.md)
- [ ] `sprint2_lp_performance.csv` and `sprint2_hp_performance.csv` exported
- [ ] Performance map plots: 3 speedlines visible
- [ ] Fouling effect visible on efficiency trend plot
- [ ] Commit: `feat(sim-sprint2): LP/HP compressor performance model`

---

## EPIC 3 — Degradation & Fault Injection
**Sprint 3 | Total Story Points: 38**

---

### US-015 — Bearing Wear Model
**Priority:** P1 | **Points:** 8 | **Status:** 📋 Backlog

**User Story:**
As a simulation engineer, I want a bearing wear model that
generates realistic vibration and temperature progression
for 3 fault cycles so that ML models have labeled fault data.

**Acceptance Criteria:**
- [ ] Healthy baseline: vib_NDE = 15–22 µm (API 670 Zone A)
- [ ] Fault ramp: Weibull-like, exponent 1.8 (accelerating)
- [ ] Peak vibration ≥ 50 µm at alarm day (API 670 Zone C boundary)
- [ ] Bearing temperature correlated with vibration (R² > 0.7)
- [ ] 3 cycles: severity 38, 45, 32 µm peak (different each cycle)
- [ ] Repair reset: vib returns to healthy baseline within 72h
- [ ] Output: vib_NDE_X(t), vib_NDE_Y(t), bearing_NDE_T(t) [8760×1]

---

### US-016 — Axial Displacement Model
**Priority:** P1 | **Points:** 3 | **Status:** 📋 Backlog

**Acceptance Criteria:**
- [ ] Healthy baseline: axial_disp = 0.04–0.06 mm
- [ ] Correlated with bearing wear (thrust bearing load)
- [ ] Alarm threshold: 0.30 mm (API 670)
- [ ] Trip threshold: 0.50 mm
- [ ] Does NOT reach trip in any cycle (alarm only)

---

### US-017 — Lube Oil System Degradation
**Priority:** P1 | **Points:** 5 | **Status:** 📋 Backlog

**Acceptance Criteria:**
- [ ] Filter ΔP: Ruth cake filtration model
  `ΔP(t) = ΔP0 × (1 + k_cake × √t_since_change)`
- [ ] 3 filter change events over 3 years
- [ ] Lube oil pressure: slight decline before filter change
- [ ] Lube oil temperature: slow rise with viscosity degradation
- [ ] Output: lube_P(t), lube_T(t), lube_filter_dP(t) [8760×1]

---

### US-018 — Seal Gas Degradation Model
**Priority:** P2 | **Points:** 3 | **Status:** 📋 Backlog

**Acceptance Criteria:**
- [ ] Primary vent ΔP: slow declining trend (seal face wear)
- [ ] Seal gas supply pressure: stable with occasional dips
- [ ] 2 seal inspection events over 3 years
- [ ] Output: seal_gas_LP_dP(t) [8760×1]

---

### US-019 — Fault Label Generator
**Priority:** P1 | **Points:** 5 | **Status:** 📋 Backlog

**User Story:**
As a data scientist, I want accurate fault labels and RUL values
for every time step so that ML models can be trained with
correct supervision.

**Acceptance Criteria:**
- [ ] fault_label = 0 (healthy): all time steps outside fault windows
- [ ] fault_label = 1 (warning): 14 days before each fault onset
- [ ] fault_label = 2 (fault): from fault onset to alarm
- [ ] rul_days = days to next alarm event, capped at 60 days
- [ ] RUL = 0 at alarm day exactly
- [ ] RUL resets to 60 after each repair
- [ ] fault_label distribution: ~78% healthy, ~4% warning, ~18% fault

---

### US-020 — Nozzle Fouling & EGT Spread
**Priority:** P2 | **Points:** 5 | **Status:** 📋 Backlog

**Acceptance Criteria:**
- [ ] EGT_spread: 5°C healthy → 45°C at max fouling
- [ ] 2 combustor wash events over 3 years
- [ ] EGT_spread positively correlated with fouling_nozzle_factor
- [ ] T_exhaust_max = T_exhaust_mean + EGT_spread/2

---

### US-021 — Sprint 3 Integration & Validation
**Priority:** P1 | **Points:** 8 | **Status:** 📋 Backlog

**Acceptance Criteria:**
- [ ] FT-01 through FT-10 all pass
- [ ] All 3 fault cycles visible in vibration plot
- [ ] Repair resets clearly visible
- [ ] Fault label distribution matches requirement (US-019)
- [ ] Commit: `feat(sim-sprint3): degradation and fault injection`

---

## EPIC 4 — Coupled System Integration
**Sprint 4 | Total Story Points: 34**

---

### US-022 — Power Balance Solver
**Priority:** P1 | **Points:** 8 | **Status:** 📋 Backlog

**User Story:**
As a simulation engineer, I want a power balance solver that
iteratively adjusts shaft speed until compressor power demand
equals turbine power supply so that the coupled system is
physically self-consistent.

**Acceptance Criteria:**
- [ ] ΔW = W_shaft - (W_LP + W_HP) < 1% at steady state
- [ ] Convergence within 3–5 iterations per time step
- [ ] Speed adjustment: ΔN proportional to ΔW
- [ ] No oscillation at steady state

---

### US-023 — Speed Controller
**Priority:** P1 | **Points:** 5 | **Status:** 📋 Backlog

**Acceptance Criteria:**
- [ ] PI controller: Kp=0.5, Ki=0.1 (tune for stability)
- [ ] Setpoint: N_demand from process model
- [ ] Anti-windup on integrator
- [ ] Speed response: settle within 5 time steps
- [ ] Output: N_actual(t) [8760×1]

---

### US-024 — Process Demand Model
**Priority:** P1 | **Points:** 5 | **Status:** 📋 Backlog

**User Story:**
As a simulation engineer, I want a process demand model that
reflects real injection well dynamics so that compressor
loading varies realistically over 3 years.

**Acceptance Criteria:**
- [ ] Q_demand(t) = f(P_reservoir, N_wells, injection_pressure)
- [ ] Includes: seasonal demand variation, well interventions (2 events)
- [ ] Overall demand trend: declining with reservoir pressure
- [ ] Short-term: step changes ±10% for operational events
- [ ] Output: Q_demand(t), P_discharge_demand(t) [8760×1]

---

### US-025 — Gearbox Model
**Priority:** P2 | **Points:** 5 | **Status:** 📋 Backlog

**Acceptance Criteria:**
- [ ] η_gearbox = 0.985 (design)
- [ ] Gearbox bearing temperatures: 6 RTD locations
- [ ] Gearbox vibration: accelerometer signals
- [ ] Gearbox degradation: slow bearing temp rise over 3 years

---

### US-026 — Full 3-Year Coupled Run
**Priority:** P1 | **Points:** 8 | **Status:** 📋 Backlog

**Acceptance Criteria:**
- [ ] INT-01 through INT-08 all pass
- [ ] Complete 26,280 time steps without divergence
- [ ] All subsystems exchange correct signals
- [ ] Commit: `feat(sim-sprint4): coupled system integration`

---

### US-027 — Simulink Model Documentation
**Priority:** P2 | **Points:** 3 | **Status:** 📋 Backlog

**Acceptance Criteria:**
- [ ] Block diagram screenshot exported as PNG
- [ ] Each subsystem annotated with equation reference
- [ ] Signal flow diagram in README
- [ ] MATLAB version and toolbox requirements documented

---

## EPIC 5 — Dataset Export & ML Pipeline Feed
**Sprint 5 | Total Story Points: 26**

---

### US-028 — MATLAB Export Script
**Priority:** P1 | **Points:** 5 | **Status:** 📋 Backlog

**Acceptance Criteria:**
- [ ] Exports all 14 ML features + fault_label + rul_days
- [ ] Plus bonus signals: W_shaft, SM, EGT_spread, ASV_pos, MW, T_amb
- [ ] Format: CSV (primary) + MAT file (archive)
- [ ] Timestamp: datetime column, hourly, 2024-01-01 start
- [ ] File: `lp_simulink_raw.csv`, `lp_simulink_raw.mat`

---

### US-029 — Python Validation Script
**Priority:** P1 | **Points:** 5 | **Status:** 📋 Backlog

**Acceptance Criteria:**
- [ ] EX-01 through EX-06 all pass automatically
- [ ] Generates validation report: signal statistics, range checks
- [ ] Converts CSV → Parquet (`lp_simulink.parquet`)
- [ ] Run: `python validate_simulink_export.py`
- [ ] Exit code 0 = all tests pass

---

### US-030 — ML Model Retraining on Simulink Data
**Priority:** P1 | **Points:** 8 | **Status:** 📋 Backlog

**User Story:**
As a data scientist, I want to retrain all ML models on the
Simulink dataset so that model performance can be compared
against the synthetic baseline.

**Acceptance Criteria:**
- [ ] anomaly_detection.py: ROC-AUC ≥ 0.85 (vs 0.831 synthetic)
- [ ] rul_lstm.py: MAE ≤ 7.0 days (vs 7.6 synthetic)
- [ ] surge_model.py: R² ≥ 0.980 (vs 0.977 synthetic)
- [ ] Comparison plot: synthetic vs Simulink metrics side-by-side
- [ ] Updated model artifacts saved to `output/simulink/`

---

### US-031 — Fleet Generator Update
**Priority:** P1 | **Points:** 3 | **Status:** 📋 Backlog

**Acceptance Criteria:**
- [ ] fleet_generator.py accepts `lp_simulink.parquet` as base dataset
- [ ] 15-unit fleet generated from Simulink data
- [ ] Circular time-shift applied correctly to new dataset
- [ ] All 15 unit files: `output/fleet_simulink/unit_01.parquet` ... `unit_15.parquet`

---

### US-032 — Before/After Comparison Report
**Priority:** P2 | **Points:** 5 | **Status:** 📋 Backlog

**Acceptance Criteria:**
- [ ] Side-by-side plots: synthetic vs Simulink signals
- [ ] ML metrics comparison table
- [ ] Narrative: "what changed and why it matters"
- [ ] File: `simulink/comparison_report.md`
- [ ] Suitable for LinkedIn post

---

## Backlog Summary

| Epic | Sprint | Story Points | User Stories | Priority P1 |
|---|---|---|---|---|
| Gas Turbine Model | 1 | 34 | 7 | 7 |
| Compressor Model | 2 | 42 | 7 | 6 |
| Degradation & Faults | 3 | 38 | 7 | 6 |
| Coupled Integration | 4 | 34 | 6 | 4 |
| Export & ML Feed | 5 | 26 | 5 | 4 |
| **Total** | | **174** | **32** | **27** |

---

## Sprint Velocity Estimate

Based on project complexity and available tooling:
```
Sprint 1: 34 points — estimated 1 session (4–6 hours)
Sprint 2: 42 points — estimated 1 session (4–6 hours)
Sprint 3: 38 points — estimated 1 session (3–5 hours)
Sprint 4: 34 points — estimated 1 session (4–6 hours)
Sprint 5: 26 points — estimated 1 session (2–4 hours)

Total estimated: 5 working sessions
```

---

## Definition of Ready (DoR)

A backlog item is Ready for sprint when:
- [ ] User story clearly written with acceptance criteria
- [ ] Physics equations referenced (paper/standard)
- [ ] Design point parameters defined
- [ ] Dependencies identified and resolved
- [ ] Story points estimated

## Definition of Done (DoD)

A backlog item is Done when:
- [ ] All acceptance criteria pass
- [ ] Code committed to GitHub
- [ ] Output file generated and validated
- [ ] No numerical instability
- [ ] Peer reviewed (domain expert sign-off)

---

## Dependencies

```
US-001 (Ambient) ─────────────────────► US-004 (Combustion)
US-002 (Fuel)    ─────────────────────► US-004 (Combustion)
US-003 (Air intake) ──────────────────► US-004 (Combustion)
US-004 (Combustion) ──────────────────► US-005 (GG Turbine)
US-005 (GG Turbine) ──────────────────► US-006 (Power Turbine)
US-006 (Power Turbine) ───────────────► US-022 (Power Balance)
US-008 (Gas Composition) ─────────────► US-009 (LP Compressor)
US-008 (Gas Composition) ─────────────► US-010 (HP Compressor)
US-009 + US-010 + US-012 ─────────────► US-013 (Anti-Surge)
US-015 + US-016 + US-017 + US-018 ───► US-019 (Fault Labels)
ALL EPICS 1-3 ────────────────────────► US-022 (Coupled System)
US-026 (Full Run) ────────────────────► US-028 (Export)
US-028 (Export) ──────────────────────► US-029 (Validation)
US-029 (Validation) ──────────────────► US-030 (ML Retrain)
```

---

*Backlog maintained per PMI-ACP Agile principles.*
*Items prioritized by business value and technical dependency.*
*Story points estimated using Planning Poker consensus.*
