# Compressor Predictive Maintenance — Portfolio

**AI-powered predictive maintenance for offshore gas compressor strings**  
Siemens SGT-400 gas turbine compressor package | Persian Gulf offshore

> Amir Sarebanzadeh, PMP® — Senior Rotating Equipment & Controls Engineer  
> 20+ years offshore oil & gas | linkedin.com/in/amir-sarebanzade

---

## The Engineering Problem

Offshore compressor packages in mature fields face two challenges:

1. **Mechanical degradation** — bearing wear, fouling, seal deterioration
2. **Off-design drift** — reservoir pressure and gas composition shift over field lifetime

Conventional threshold alarms give 2–6 hours of warning.  
This system targets **14–65 days** of advance warning.

---

## What's in This Repository

### ML Pipeline (Python · PyTorch · scikit-learn)

| File | Description |
|---|---|
| `compressor_design_basis.py` | Thermodynamic design parameters (ASME PTC-10 / API 617) |
| `data_generator.py` | Physics-based synthetic dataset — 3 years, 3 fault cycles |
| `fleet_generator.py` | 15-unit fleet via circular time-shift |
| `anomaly_detection.py` | Isolation Forest + LSTM Autoencoder |
| `rul_lstm.py` | LSTM Remaining Useful Life prediction |
| `surge_model.py` | Physics-informed surge margin (Greitzer + Gradient Boosting) |

### Simulink Physics Model (MATLAB/Octave)

| File | Description |
|---|---|
| `SIMULINK_ROADMAP.md` | 5-sprint plan, 45 acceptance tests |
| `SIMULINK_BACKLOG.md` | 32 user stories, 174 story points (PMI-ACP Agile) |
| `SIMULINK_SIGNAL_ARCHITECTURE.md` | 65 parameters, 8 signal groups |
| `ARCHITECTURE.md` | 6-layer model separation |

---

## ML Results (Simulink physics-based dataset)

| Model | Metric | Result |
|---|---|---|
| LSTM Autoencoder | ROC-AUC | **0.861** |
| RUL LSTM | MAE | **6.61 days** |
| Surge PIML | MAE improvement over physics-only | **94.4%** |

Simulink model: **35/35 acceptance tests passing**  
Dataset: 26,280 rows × 18 columns | 3 years | 3 bearing fault cycles

---

## Physics Models Used

- **Gas Turbine**: Brayton cycle (open, twin-shaft)
- **Compressor**: Schultz polytropic method (ASME PTC-10)
- **Surge**: Greitzer (1976) B-parameter
- **Fouling**: Tarabrin et al. (1998) exponential decay
- **Reservoir decline**: Arps (1945) exponential
- **Bearing wear**: ISO 13373 / API 670 severity zones

---

## Tech Stack

**SCADA/HMI:** Ignition Perspective · OPC-UA · Siemens S7-1500  
**ML:** Python · PyTorch · scikit-learn · pandas  
**Physics:** MATLAB/Octave · Simulink  
**Cloud:** Azure / Derak (Iranian cloud) · PostgreSQL · MinIO  
**Dashboard:** Power BI · matplotlib  
**Standards:** ASME PTC-10 · API 617 · API 670 · IEC 61511

---

*Note: The full private repository includes Ignition HMI source,*  
*signal lists, and engineering documents — not published here*  
*for confidentiality reasons.*
