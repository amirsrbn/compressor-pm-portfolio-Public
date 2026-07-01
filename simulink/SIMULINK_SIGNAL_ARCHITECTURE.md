# Simulink Model — Signal Architecture & Input Classification

**Project:** SGT-400 Gas Turbine Compressor Package  
**Document:** Signal Architecture — Inputs, Disturbances, Outputs  
**Author:** Amir Sarebanzadeh, PMP®  
**Date:** 2026-06-28

---

## Architectural Principle

```
┌─────────────────────────────────────────────────────────────────┐
│                    SIMULINK MODEL BOUNDARY                       │
│                                                                  │
│  DISTURBANCE INPUTS          MAIN MODEL INPUTS                  │
│  (Environmental noise)       (Compressor physics)               │
│                                                                  │
│  Group 1: Process      ──►  ┌─────────────────────┐            │
│  Group 2: Mechanical   ──►  │                     │            │
│  Group 3: Lube Oil     ──►  │   GAS TURBINE       │            │
│  Group 4: Seal Gas     ──►  │   COMPRESSOR        │  ──► OUTPUTS│
│  Group 5: Anti-Surge   ──►  │   COUPLED MODEL     │            │
│  Group 6: Gas Turbine  ──►  │                     │            │
│  Group 7: Ambient      ──►  └─────────────────────┘            │
│  Group 8: Event Log    ──►                                      │
│                                                                  │
│  COMPRESSOR MAIN INPUTS (determined by thermodynamic laws):     │
│  • Shaft speed N(t)                                             │
│  • Inlet pressure P_in(t)                                       │
│  • Inlet temperature T_in(t)                                    │
│  • Gas composition MW(t), γ(t), Z(t)                           │
│  • Mass flow demand Q_demand(t)                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## PART A — Compressor Main Model Inputs
*(These are the primary physics-driven inputs — computed internally)*

The centrifugal compressor model (Schultz polytropic, ASME PTC-10) 
requires these inputs at every time step. They are NOT external 
disturbances — they are computed from the coupled system:

```
┌─────────────────────────────────────────────────────────────────┐
│  COMPRESSOR MAIN INPUTS                                         │
├─────────────────┬──────────┬────────────────────────────────────┤
│ Parameter       │ Unit     │ Source in coupled model            │
├─────────────────┼──────────┼────────────────────────────────────┤
│ N_shaft         │ rpm      │ Speed controller + power balance   │
│ P_suction_LP    │ bara     │ Reservoir model (Arps decline)     │
│ T_suction_LP    │ °C       │ Separator + ambient + cooler model │
│ P_suction_HP    │ bara     │ = P_discharge_LP - ΔP_intercooler  │
│ T_suction_HP    │ °C       │ LP discharge + intercooler model   │
│ Q_demand        │ am³/hr   │ Process demand model               │
│ MW_gas          │ kg/kmol  │ Gas composition model (reservoir)  │
│ gamma_gas       │ —        │ Derived from MW and T, P           │
│ Z_inlet         │ —        │ BWRS equation of state             │
│ fouling_factor  │ 0–1      │ Fouling accumulation model         │
└─────────────────┴──────────┴────────────────────────────────────┘
```

---

## PART B — Eight Disturbance Input Groups
*(These enter the model as time-varying disturbances or noise)*

---

### GROUP 1 — Process Signals (10 parameters)
**Role:** Primary process measurements — define operating point  
**Model entry point:** Directly into thermodynamic equations

| # | Parameter | Unit | Simulink Input Type | Effect on model |
|---|---|---|---|---|
| 1 | Suction pressure LP | bara | Slow drift + noise | Compression ratio, flow |
| 2 | Discharge pressure LP | bara | Slow drift + noise | Compression ratio, head |
| 3 | Suction temperature LP | °C | Seasonal + noise | Polytropic head, efficiency |
| 4 | Discharge temperature LP | °C | Computed + noise | Efficiency validation |
| 5 | Suction pressure HP | bara | = f(P_discharge_LP) | HP compression ratio |
| 6 | Discharge pressure HP | bara | Slow drift + noise | HP head |
| 7 | Suction temperature HP | °C | = f(T_discharge_LP, cooler) | HP efficiency |
| 8 | Discharge temperature HP | °C | Computed + noise | HP efficiency check |
| 9 | Mass flow / volume flow | am³/hr | Process demand driven | Flow coefficient φ |
| 10 | Gas composition (MW) | kg/kmol | Reservoir aging model | Thermodynamic properties |

**Simulink implementation:**
```matlab
% Group 1 inputs — time arrays [8760×1]
P_suc_LP(t)  = P_reservoir(t) + ΔP_flowline   % Arps decline
T_suc_LP(t)  = T_wellhead + ΔT_pipeline + noise(σ=0.35°C)
MW_gas(t)    = 21.9 + 1.5*(t/8760) + noise(σ=0.3)
% gamma, Z computed from MW, T, P via BWRS
```

---

### GROUP 2 — Mechanical Signals (15 parameters)
**Role:** Rotating equipment health monitoring  
**Model entry point:** Rotordynamics sub-model + bearing model

| # | Parameter | Unit | Simulink Input Type | Effect on model |
|---|---|---|---|---|
| 1 | Vibration NDE-X LP | µm | Bearing wear model | Fault label, RUL |
| 2 | Vibration NDE-Y LP | µm | Bearing wear model | 2D orbit analysis |
| 3 | Vibration DE-X LP | µm | Bearing wear model (coupled to NDE) | Fault detection |
| 4 | Vibration DE-Y LP | µm | Bearing wear model | Fault detection |
| 5 | Vibration NDE-X HP | µm | Separate bearing model | HP fault detection |
| 6 | Vibration NDE-Y HP | µm | Bearing wear model | HP fault detection |
| 7 | Vibration DE-X HP | µm | Bearing wear model | HP fault detection |
| 8 | Vibration DE-Y HP | µm | Bearing wear model | HP fault detection |
| 9 | Axial displacement LP-A | mm | Thrust bearing model | Axial load |
| 10 | Axial displacement LP-B | mm | Thrust bearing model (redundant) | Voting |
| 11 | Axial displacement HP-A | mm | Thrust bearing model | Axial load |
| 12 | Axial displacement HP-B | mm | Thrust bearing model (redundant) | Voting |
| 13 | Shaft speed ST-01 | rpm | Speed controller output | Performance map |
| 14 | Shaft speed ST-02 | rpm | = ST-01 ± speed control error | Redundancy check |
| 15 | Gearbox vibration | µm | Gearbox bearing model | Gearbox health |

**Simulink implementation:**
```matlab
% Bearing wear model — Weibull-like fault ramp
vib_NDE_X(t) = vib_healthy + noise(σ=0.9*scale)
             + A_fault * ((t-t_fault)/(t_alarm-t_fault))^1.8  % if t > t_fault
             
% 3 fault cycles — different severity
fault_cycles = [300, 342, 38;   % [fault_day, alarm_day, peak_vib_µm]
                645, 687, 45;
                992, 1034, 32];
```

---

### GROUP 3 — Lube Oil System (5 parameters)
**Role:** Supporting system health  
**Model entry point:** Lube oil sub-model (separate from compressor thermodynamics)

| # | Parameter | Unit | Simulink Input Type | Effect on model |
|---|---|---|---|---|
| 1 | Lube oil supply pressure | bara | PI control + degradation | Bearing protection |
| 2 | Lube oil supply temperature | °C | Heat exchanger model | Oil viscosity |
| 3 | Lube oil filter ΔP | bar | Ruth cake filtration | Filter change trigger |
| 4 | Lube oil tank level | % | Mass balance model | Alarm trigger |
| 5 | Lube oil cooler outlet temp | °C | Heat exchanger model | Viscosity validation |

**Simulink implementation:**
```matlab
% Ruth cake filtration model
lube_filter_dP(t) = dP0 * (1 + k_cake * sqrt(t_since_change))
% 3 filter change events → step reset

% Oil temperature — viscosity degradation (Arrhenius)
T_lube(t) = T_lube_design + ΔT_aging * (1-exp(-k_ox*t)) + noise(σ=0.5)
```

---

### GROUP 4 — Seal Gas System (4 parameters)
**Role:** Dry gas seal health monitoring  
**Model entry point:** Seal gas sub-model

| # | Parameter | Unit | Simulink Input Type | Effect on model |
|---|---|---|---|---|
| 1 | Seal gas supply pressure LP | bara | Control valve + degradation | Seal integrity |
| 2 | Primary vent ΔP LP | bara | Seal wear model | Seal degradation trend |
| 3 | Seal gas supply pressure HP | bara | Control valve + degradation | Seal integrity |
| 4 | Primary vent ΔP HP | bara | Seal wear model | Seal degradation trend |

**Simulink implementation:**
```matlab
% Seal degradation — linear wear model
vent_dP_LP(t) = vent_dP_new * (1 + k_seal * t_service_hours/8760)
% 2 seal inspection events → partial reset
```

---

### GROUP 5 — Anti-Surge System (5 parameters)
**Role:** Process safety — surge prevention  
**Model entry point:** Anti-surge controller sub-model

| # | Parameter | Unit | Simulink Input Type | Effect on model |
|---|---|---|---|---|
| 1 | ASV position LP Train A | % | PI controller output | Recycle flow |
| 2 | ASV position LP Train B | % | PI controller output | Recycle flow |
| 3 | ASV position HP Train A | % | PI controller output | Recycle flow |
| 4 | ASV position HP Train B | % | PI controller output | Recycle flow |
| 5 | Recycle flow LP | am³/hr | = f(ASV_position, ΔP) | Surge margin |

**Simulink implementation:**
```matlab
% Surge margin computation
SM(t) = (Q_actual(t) - Q_surge_effective(t)) / Q_surge_effective(t) * 100

% Anti-surge controller
if SM < 10
    ASV_pos = ASV_pos + Kp * (10 - SM)   % proportional open
end
if SM < 5
    ASV_pos = 100   % emergency full open
end
```

---

### GROUP 6 — Gas Turbine Driver (6 parameters)
**Role:** Driver performance and health  
**Model entry point:** Gas turbine sub-model (Brayton cycle)

| # | Parameter | Unit | Simulink Input Type | Effect on model |
|---|---|---|---|---|
| 1 | Fuel gas pressure | bara | Supply model + control valve | Combustion stability |
| 2 | Fuel gas flow | Nm³/hr | Combustion model | Heat rate, shaft power |
| 3 | Exhaust temperature mean | °C | Power turbine expansion | Hot section health |
| 4 | EGT spread | °C | Nozzle fouling model | Combustor health |
| 5 | Power turbine speed | rpm | = Shaft speed (direct drive) | Performance |
| 6 | Shaft power output | kW | Brayton cycle output | Power balance |

**Simulink implementation:**
```matlab
% Brayton cycle — twin shaft
W_shaft(t) = m_gas * Cp_gas * (T4(t)-T5(t)) * eta_pt * eta_mech
T_exhaust(t) = T5(t) + noise(σ=1.5)
EGT_spread(t) = EGT0 + k_nozzle * fouling_nozzle(t)
```

---

### GROUP 7 — Ambient & Utility (3 parameters)
**Role:** External disturbances — performance correction  
**Model entry point:** All sub-models (ambient affects everything)

| # | Parameter | Unit | Simulink Input Type | Effect on model |
|---|---|---|---|---|
| 1 | Ambient temperature | °C | Seasonal + diurnal model | Air density, GT power |
| 2 | Ambient pressure | bara | Slow seasonal variation | Air density |
| 3 | Cooling water inlet temp | °C | Sea water temperature model | Intercooler, lube cooler |

**Simulink implementation:**
```matlab
% Persian Gulf ambient — seasonal + diurnal
T_amb(t) = 35 + 10*sin(2*pi*t/8760)      % seasonal: summer peak
          + 8*sin(2*pi*t/24)               % diurnal: day/night
          + randn(size(t)) * 1.5           % measurement noise [°C]

P_amb(t) = 1.013 - 0.005*sin(2*pi*t/8760) + randn(size(t))*0.002

% Cooling water — Persian Gulf sea temperature
T_seawater(t) = 28 + 6*sin(2*pi*t/8760) + randn(size(t))*0.5
```

---

### GROUP 8 — Event Log & Labels (7 parameters)
**Role:** Ground truth for ML training — NOT measured signals  
**Model entry point:** Post-processing / label generator

| # | Parameter | Unit | Simulink Input Type | Purpose |
|---|---|---|---|---|
| 1 | fault_label | 0/1/2 | Rule-based from vib, RUL | ML training label |
| 2 | rul_days | days | Computed from alarm schedule | RUL model target |
| 3 | trip_flag | bool | From alarm threshold crossing | Event detection |
| 4 | startup_flag | bool | From speed ramp model | Cycle counting |
| 5 | shutdown_flag | bool | From speed ramp model | Cycle counting |
| 6 | maintenance_flag | bool | From fault injection schedule | Repair events |
| 7 | water_wash_flag | bool | From fouling threshold | Wash event marker |

**Simulink implementation:**
```matlab
% Fault label generator
fault_label = zeros(N_hours, 1);
for each fault_cycle:
    warn_start = fault_day - 14;      % 14-day warning
    fault_label(warn_start:fault_day) = 1;   % warning
    fault_label(fault_day:alarm_day)  = 2;   % active fault

% RUL — days to next alarm
for each alarm_event:
    for h = max(0, alarm_h - 60*24) : alarm_h:
        rul_days(h) = min(rul_days(h), (alarm_h - h)/24)
```

---

## PART C — Signal Flow Summary

```
EXTERNAL DISTURBANCES (time-varying inputs)
│
├── GROUP 7: Ambient [T_amb, P_amb, T_seawater]
│       │
│       ▼
├── GROUP 6: Gas Turbine [W_shaft(t), T_exhaust(t), EGT_spread(t)]
│       │
│       ▼ (shaft power)
│
├── GROUP 1: Process [P, T, MW, Q] ──────────────────────────────►┐
│                                                                  │
│   ┌──────────────────────────────────────────────────────┐     │
│   │         COMPRESSOR MAIN MODEL                        │◄────┘
│   │   Schultz polytropic + Greitzer surge                │
│   │   Inputs: N, P_in, T_in, MW, γ, Z, fouling          │
│   │   Outputs: P_out, T_out, η_p, SM, Q_actual          │
│   └──────────────────────────────────────────────────────┘
│           │
│   ┌───────┴────────────────────────────────────┐
│   │                                             │
├── GROUP 2: Mechanical [vib, displacement, speed]│
├── GROUP 3: Lube Oil [P, T, ΔP, level]          │
├── GROUP 4: Seal Gas [supply P, vent ΔP]        │
├── GROUP 5: Anti-Surge [ASV pos, recycle flow]  │
│                                                 │
│   └─────────────────────────────────────────────┘
│                   │
├── GROUP 8: Labels [fault_label, rul_days, flags]◄─ post-process
│
▼
DATASET OUTPUT [26,280 rows × 55 parameters]
→ filtered to 14 ML features + labels for pipeline
```

---

## PART D — Parameter Count Summary

| Group | Description | Parameters | Role |
|---|---|---|---|
| Main Model | Compressor physics inputs | 10 | Computed internally |
| Group 1 | Process signals | 10 | Primary disturbance |
| Group 2 | Mechanical signals | 15 | Fault detection |
| Group 3 | Lube oil system | 5 | Supporting system |
| Group 4 | Seal gas system | 4 | Seal health |
| Group 5 | Anti-surge system | 5 | Process safety |
| Group 6 | Gas turbine driver | 6 | Driver performance |
| Group 7 | Ambient & utility | 3 | External disturbance |
| Group 8 | Event log & labels | 7 | ML ground truth |
| **Total** | | **65** | |

**ML pipeline uses:** 14 features + fault_label + rul_days = 16 columns  
**Full Simulink dataset:** 65 parameters (rich — for analysis and future models)

---

## PART E — Noise Model per Group

Each group has a specific noise characteristic:

| Group | Noise Type | Typical σ | Physical Basis |
|---|---|---|---|
| Process | Gaussian + slow drift | 0.3–0.5% | Transmitter accuracy |
| Mechanical | Gaussian + fault ramp | 5% (healthy) | Proximity probe noise |
| Lube Oil | Gaussian + step changes | 0.3–2% | PT/TT accuracy + filter change |
| Seal Gas | Gaussian + trend | 3% | PDT accuracy |
| Anti-Surge | Deterministic (controller) | — | Digital setpoint |
| Gas Turbine | Gaussian + fouling trend | 1.5°C | TC accuracy |
| Ambient | Seasonal + diurnal + Gaussian | 1.5°C | Met station |
| Labels | Deterministic | 0 | Computed from schedule |

---

*This architecture document is the engineering basis for all*
*Simulink model development. All sprint backlog items (SIMULINK_BACKLOG.md)*
*implement sub-models defined here.*

*Standards reference: ASME PTC-10, API 670, API 617, ISO 13709*
