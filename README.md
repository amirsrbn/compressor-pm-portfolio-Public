# SGT-400 Turbo-Compressor Digital Twin & Predictive Maintenance

**Independent Engineering Research & Development Portfolio**

**Developed by Amir Sarebanzadeh**  
Electronics Engineer | Industrial Instrumentation & Control Systems | Digital Twin Development  
[LinkedIn](https://www.linkedin.com/in/amir-sarebanzade)

## Overview

This public repository presents **selected source code and engineering documentation** from my independently developed research platform for gas turbine-driven offshore compressor trains.

The broader project explores physics-informed dynamic modelling, gas turbine and LP/HP compressor behaviour, industrial control systems, fault injection, predictive maintenance, and industrial software integration.

The development work spans MATLAB/Simulink, Python-based analytics, OPC-UA interfaces, Ignition Perspective HMI, and automated verification activities, including simulated scenarios involving a virtual fleet of 15 compressor units.

> **Status and scope:** The broader platform is under active research and development. Individual components have been tested within stated boundaries, but integrated end-to-end qualification is ongoing. It has **not** been deployed as an operational industrial system. The Simulink execution models, live-control implementations, and most integration evidence are **not published in this public repository**.

## Engineering motivation

Offshore rotating-equipment systems experience changing operating conditions, equipment degradation, instrumentation faults, and control-system interactions. The research investigates how simulation and data-driven methods may help study these effects and support fault detection, remaining useful life estimation, and engineering decision-making.

The examples here are **research prototypes and simulated-data experiments**, not manufacturer-approved models or field-proven performance guarantees.

## What's actually available here

### Python: modelling and predictive-maintenance experiments

| Public file | Purpose |
| --- | --- |
| [`compressor_design_basis.py`](ml_pipeline/compressor_design_basis.py) | Parameters and assumptions used by the research examples |
| [`data_generator.py`](ml_pipeline/data_generator.py) | Generation of synthetic equipment and fault-related data |
| [`fleet_generator.py`](ml_pipeline/fleet_generator.py) | Virtual multi-unit dataset/scenario generation |
| [`anomaly_detection.py`](ml_pipeline/anomaly_detection.py) | Anomaly-detection experiments |
| [`rul_lstm.py`](ml_pipeline/rul_lstm.py) | Remaining useful life modelling experiment |
| [`surge_model.py`](ml_pipeline/surge_model.py) | Physics-informed surge-related modelling experiment |

### Engineering documentation

| Public document | Purpose |
| --- | --- |
| [`ARCHITECTURE.md`](simulink/ARCHITECTURE.md) | Architectural concepts and model separation |
| [`SIMULINK_SIGNAL_ARCHITECTURE.md`](simulink/SIMULINK_SIGNAL_ARCHITECTURE.md) | Signal architecture and interface planning |
| [`SIMULINK_ROADMAP.md`](simulink/SIMULINK_ROADMAP.md) | Historical development roadmap |
| [`SIMULINK_BACKLOG.md`](simulink/SIMULINK_BACKLOG.md) | Historical work planning and acceptance targets |

**Important:** Planning documents describe intended scope at the time they were written; they should not be read as proof that every item has been implemented or accepted.

## System concept

The private development program covers these related engineering areas:

1. **Dynamic equipment models:** gas turbine and compressor behaviour, operating-point changes, and degradation scenarios.
2. **Industrial instrumentation and controls:** sensor and actuator signals, controller logic, and abnormal-condition scenarios.
3. **Fault injection and data generation:** controlled studies of fault progression and simulated equipment observations.
4. **Predictive-maintenance analytics:** anomaly detection and remaining useful life research.
5. **Integration and visualisation:** work involving OPC-UA and Ignition Perspective HMI.
6. **Verification:** automated checks, MATLAB/Simulink tests, and staged integration assessment.

These are **project areas**, not a claim that the full chain has been qualified as one deployed product.

## Historical experimental results

An earlier research snapshot reported the following **simulation-based** metrics:

| Experiment | Historical reported metric | Result |
| --- | --- | --- |
| LSTM autoencoder anomaly detection | ROC-AUC | **0.861** |
| LSTM remaining useful life prediction | Mean absolute error | **6.61 days** |
| Physics-informed surge experiment | MAE improvement versus its physics-only comparison | **94.4%** |

**Testing progress:** The project owner reports approximately **2,000 successful test checks/executions across the wider private development program**. This is a cumulative, owner-reported figure, **not yet independently reconciled into a deduplicated, auditable test count**. It spans different development phases and test types and is **not** a claim of 2,000 distinct current-version tests or complete integrated-system qualification. The latest scoped evidence is tracked in the private project's test manifests and capability/evidence records.

The three numerical ML figures above are retained for **historical context only**. They relate to earlier model, dataset, and test configurations; they are **not current acceptance results**, independently reproduced benchmarks, field-validation results, or guaranteed performance on real equipment. In particular, the surge comparison is specific to its original experimental baseline and must not be generalized to industrial performance.

The broader private development subsequently adopted additional simulation/data revisions (including a documented **26,280-row, 119-column** physics-data artifact). That artifact and its associated verification evidence are **not included here**; therefore this README does not present it as a publicly reproducible result.

## Tools and engineering methods

**Published Python examples:** Python-based modelling, synthetic data, anomaly detection, and RUL/surge experiments.  
**Broader private development:** MATLAB/Simulink; control-system simulation; OPC-UA; Ignition Perspective HMI; automated engineering tests.

**Not claimed:** an Azure Machine Learning deployment, production cloud infrastructure, an OEM-certified digital twin, or a commissioned plant installation.

## Public/private boundary and confidentiality

This repository is a **selected public portfolio**, not a release of the complete engineering system. The full development repository contains additional models, engineering documents, control/integration work, and detailed test evidence. Those materials are not made public here.

Public examples are intended to illustrate engineering methods and development approach. No public code or data should be interpreted as operational instructions for a real compressor train without independent engineering review, safety assessment, and validation.

## Contact

**Amir Sarebanzadeh**  
[LinkedIn](https://www.linkedin.com/in/amir-sarebanzade) · [GitHub profile](https://github.com/amirsrbn)
