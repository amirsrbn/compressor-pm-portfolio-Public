# Engineering Architecture — Public Overview

**SGT-400 Turbo-Compressor Digital Twin & Predictive Maintenance**  
**Independent engineering research and development | Public, non-operational summary**

## Purpose

This document summarizes the engineering approach of the wider private R&D project. It is not a design package, equipment configuration, safety procedure, or claim of completed plant qualification.

## System layers

1. **Physical models:** dynamic modelling of gas turbine, LP/HP compressor and associated process interactions, including off-design scenarios.
2. **Instrumentation and control:** separation of simulated plant states, measurements, controls, and protective functions; study of command and feedback quality.
3. **Fault scenarios:** configurable equipment, sensing and actuation disturbances with reproducible simulation runs.
4. **Analytical pipeline:** synthetic-data generation, anomaly detection and remaining-useful-life experiments.
5. **Integration:** staged evaluation of interfaces involving MATLAB/Simulink, Python, OPC-UA and Ignition Perspective.
6. **Verification:** validation at component, simulation, communication and system-integration boundaries.

## Engineering principles

- Distinguish true simulated quantities from noisy or biased measurements.
- Keep controller authority, communication quality, and protective behaviours explicit.
- Separate research assumptions from OEM or site-verified engineering data.
- Evaluate fault scenarios against clearly stated model and test boundaries.
- Treat a passed unit test, successful scenario, and fully validated system as distinct claims.

## Published materials

The [Python examples](../ml_pipeline/) demonstrate selected modelling and predictive-maintenance research methods. The integrated dynamic plant model and most runtime/integration source files remain in the private development repository and are not available here.

## Status

Research and staged verification are ongoing. This public overview does **not** claim a fully validated end-to-end platform, safety certification, OEM endorsement, or a production installation.

For documented validation snapshots, see [Development Status & Verification](DEVELOPMENT_STATUS_AND_VERIFICATION.md).
