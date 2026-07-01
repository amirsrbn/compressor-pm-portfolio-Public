"""
compressor_design_basis.py
==========================
Physics-based design parameters for a twin-shaft gas turbine driven
centrifugal compressor string in Persian Gulf offshore service.

Compressor type : Vertically-split multi-stage centrifugal, two-body string
Driver          : Industrial twin-shaft gas turbine, 10–15 MW class
Application     : Gas compression — offshore platform, Middle East
Test standard   : ASME PTC-10 Type-2, API 617

Note
----
All numerical values are derived from the author's own engineering
calculations and physics-based modelling, informed by publicly available
thermodynamic standards (ASME PTC-10, API 617, ISO 5167) and general
OEM documentation in the open literature.
No proprietary vendor test data, client documents, or confidential
contractual information is reproduced here.
"""

import numpy as np

# ── Gas properties at design inlet (associated gas, Persian Gulf field) ───────
# Derived via BWRS equation of state (Starling, 1973) — public domain method
LP_GAS = {
    "description"        : "Associated gas — LP stage inlet (field conditions)",
    "molecular_weight"   : 21.9,          # kg/kmol  — typical Persian Gulf gas
    "isentropic_exponent": 1.31,
    "polytropic_exponent": 1.31,
    "Z_inlet"            : 0.95,
    "Z_discharge"        : 0.95,
}

HP_GAS = {
    "description"        : "Associated gas — HP stage inlet (inter-stage conditions)",
    "molecular_weight"   : 20.3,          # kg/kmol
    "isentropic_exponent": 1.42,
    "polytropic_exponent": 1.68,
    "Z_inlet"            : 0.89,
    "Z_discharge"        : 0.97,
}

# ── LP Compressor — design operating point ────────────────────────────────────
# 5-stage vertically-split centrifugal compressor
# Values computed from thermodynamic first principles at guaranteed duty
LP_DESIGN = {
    "stages"                    : 5,
    "first_impeller_dia_mm"     : 335,
    "inlet_pressure_bara"       : 17.5,
    "inlet_temperature_C"       : 28.9,
    "discharge_pressure_bara"   : 50.5,
    "discharge_temperature_C"   : 116.0,
    "speed_rpm"                 : 13000,
    "mass_flow_kg_hr"           : 136_684,
    "inlet_volume_flow_am3_hr"  : 8_477,
    "pressure_ratio"            : 2.886,
    "polytropic_head_kJ_kg"     : 130.8,
    "polytropic_efficiency_pct" : 81.4,
    "shaft_power_kW"            : 6_100,
    "inlet_density_kg_m3"       : 16.07,
    "discharge_density_kg_m3"   : 36.00,
    "machine_mach_number"       : 0.604,
    "machine_reynolds"          : 9.39e6,
    "flow_coefficient"          : 0.117,
    # Alarm / trip thresholds (API 670 / OEM typical)
    "vib_alarm_um"              : 50,
    "vib_trip_um"               : 75,
    "bearing_temp_alarm_C"      : 85,
    "bearing_temp_trip_C"       : 95,
    "axial_disp_alarm_mm"       : 0.30,
    "axial_disp_trip_mm"        : 0.50,
    "lube_oil_pressure_alarm_bara" : 1.8,
    "lube_oil_pressure_trip_bara"  : 1.5,
    "lube_oil_filter_dP_alarm_bar" : 0.50,
}

# ── HP Compressor — design operating point ────────────────────────────────────
# 6-stage vertically-split centrifugal compressor
HP_DESIGN = {
    "stages"                    : 6,
    "first_impeller_dia_mm"     : 335,
    "inlet_pressure_bara"       : 48.8,
    "inlet_temperature_C"       : 43.9,
    "discharge_pressure_bara"   : 129.2,
    "discharge_temperature_C"   : 162.0,
    "speed_rpm"                 : 13000,
    "mass_flow_kg_hr"           : 25_249,
    "inlet_volume_flow_am3_hr"  : 600,
    "pressure_ratio"            : 2.648,
    "polytropic_head_kJ_kg"     : 137.4,
    "polytropic_efficiency_pct" : 55.6,
    "shaft_power_kW"            : 1_735,
    "inlet_density_kg_m3"       : 42.27,
    "discharge_density_kg_m3"   : 74.81,
    "machine_mach_number"       : 0.563,
    "machine_reynolds"          : 4.99e6,
    "flow_coefficient"          : 0.008,
    # Alarm / trip thresholds
    "vib_alarm_um"              : 50,
    "vib_trip_um"               : 75,
    "bearing_temp_alarm_C"      : 90,
    "bearing_temp_trip_C"       : 100,
    "axial_disp_alarm_mm"       : 0.30,
    "axial_disp_trip_mm"        : 0.50,
    "lube_oil_pressure_alarm_bara" : 1.8,
    "lube_oil_pressure_trip_bara"  : 1.5,
    "lube_oil_filter_dP_alarm_bar" : 0.50,
}

# ── Speed lines for performance map ──────────────────────────────────────────
# Derived from similarity laws (ASME PTC-10 Section 5)
LP_SPEEDLINES = [
    {"speed_pct": 80,   "speed_rpm": 10_400, "head_factor": 0.65, "eta_factor": 0.93},
    {"speed_pct": 93.4, "speed_rpm": 13_000, "head_factor": 1.00, "eta_factor": 1.00},
    {"speed_pct": 105,  "speed_rpm": 14_615, "head_factor": 1.22, "eta_factor": 0.97},
]

HP_SPEEDLINES = [
    {"speed_pct": 80,   "speed_rpm": 10_400, "head_factor": 0.65, "eta_factor": 0.91},
    {"speed_pct": 93.4, "speed_rpm": 13_000, "head_factor": 1.00, "eta_factor": 1.00},
    {"speed_pct": 105,  "speed_rpm": 14_615, "head_factor": 1.22, "eta_factor": 0.96},
]

# ── Measurement tolerances (ASME PTC-10 Table 3.2) ───────────────────────────
# These are standard published tolerances — not proprietary
MEASUREMENT_TOLERANCES = {
    "pressure_pct"      : 0.30,
    "temperature_C"     : 0.35,
    "mass_flow_pct"     : 0.96,
    "volume_flow_pct"   : 0.96,
    "polytropic_head_pct": 0.70,
    "power_pct"         : 1.03,
}

# ── Helper: isentropic efficiency from polytropic ─────────────────────────────
def poly_to_isen_efficiency(eta_p, pressure_ratio, n_p):
    """Convert polytropic to isentropic efficiency (PTC-10 method)."""
    gamma = n_p / (n_p - 1)
    rp_gamma = pressure_ratio ** (1 / gamma)
    eta_s = (rp_gamma - 1) / (pressure_ratio ** ((n_p - 1) / n_p) - 1) * eta_p
    return eta_s

# ── Helper: performance at off-design speed (similarity laws) ─────────────────
def off_design_performance(design: dict, speed_ratio: float):
    """
    Estimate off-design head and flow using fan/compressor similarity laws.
    speed_ratio = N_actual / N_design
    """
    return {
        "speed_rpm"           : design["speed_rpm"] * speed_ratio,
        "mass_flow_kg_hr"     : design["mass_flow_kg_hr"] * speed_ratio,
        "polytropic_head_kJ_kg": design["polytropic_head_kJ_kg"] * speed_ratio**2,
        "shaft_power_kW"      : design["shaft_power_kW"] * speed_ratio**3,
        "pressure_ratio"      : 1 + (design["pressure_ratio"] - 1) * speed_ratio**2,
    }


if __name__ == "__main__":
    print("=" * 58)
    print("  Centrifugal Compressor String — Design Point Summary")
    print("  Persian Gulf Offshore | Twin-shaft GT driven")
    print("=" * 58)

    for label, d in [("LP (5-stage)", LP_DESIGN), ("HP (6-stage)", HP_DESIGN)]:
        print(f"\n{label}:")
        print(f"  Inlet     : {d['inlet_pressure_bara']} bara / {d['inlet_temperature_C']} °C")
        print(f"  Discharge : {d['discharge_pressure_bara']} bara / {d['discharge_temperature_C']} °C")
        print(f"  Speed     : {d['speed_rpm']:,} rpm")
        print(f"  Flow      : {d['mass_flow_kg_hr']:,} kg/hr")
        print(f"  Pr ratio  : {d['pressure_ratio']:.3f}")
        print(f"  Poly η    : {d['polytropic_efficiency_pct']:.1f}%")
        print(f"  Power     : {d['shaft_power_kW']:,} kW")

    print("\nOff-design example — LP at 80% speed:")
    od = off_design_performance(LP_DESIGN, 0.80)
    for k, v in od.items():
        print(f"  {k}: {v:,.1f}")
