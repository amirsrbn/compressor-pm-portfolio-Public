"""
fleet_generator.py
==================
Generates realistic time-series data for a fleet of 15 compressor units
using circular time-shifting of a single physics-based base dataset.

Concept
-------
All 15 units share the same underlying degradation physics (extracted from
real performance test data). Each unit is offset by 2 months in the
degradation cycle, creating a fleet where -- at any given moment -- units
are in different stages of their maintenance lifecycle.

Unit-specific noise seeds ensure measurement signals differ between units
even when they are at the same degradation stage.

Circular shift: when a unit's offset exceeds the dataset length, it wraps
around to the beginning, simulating the next maintenance cycle.

Modes
-----
Default (no flags):
  Base: output/lp_multiyear.parquet (synthetic, old schema)
  Out:  output/fleet/unit_01.parquet ... unit_15.parquet

--simulink mode:
  Base: lp_simulink.parquet (MATLAB physics-based, 18-column schema)
  Out:  output/fleet_simulink/unit_01.parquet ... unit_15.parquet

Usage:
  python fleet_generator.py
  python fleet_generator.py --simulink
  python fleet_generator.py --simulink --base /path/to/lp_simulink.parquet

Author : Amir Sarabandi
"""

import argparse
import numpy as np
import pandas as pd
from pathlib import Path

OUT = Path("output")
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Shared configuration
# ---------------------------------------------------------------------------
N_UNITS         = 15
SHIFT_MONTHS    = 2
HOURS_PER_MONTH = 30 * 24          # 720 h/month
UNIT_SHIFT_H    = SHIFT_MONTHS * HOURS_PER_MONTH   # 1440 h/unit

UNIT_NOISE_SCALE = {
    i: 1.0 + (i - 8) * 0.03        # T01=0.79 ... T15=1.21
    for i in range(1, N_UNITS + 1)
}

# ---------------------------------------------------------------------------
# Old-schema (synthetic) configuration
# ---------------------------------------------------------------------------
FEATURES = [
    "vib_NDE_X_um", "vib_NDE_Y_um", "vib_DE_X_um", "vib_DE_Y_um",
    "axial_disp_A_mm", "axial_disp_B_mm",
    "bearing_NDE_T_C", "bearing_DE_T_C",
    "poly_eta_realtime_pct", "discharge_T_C", "inlet_P_bara",
    "lube_P_bara", "lube_filter_dP_bar", "seal_gas_LP_dP_bar",
    "fault_label", "rul_days",
]

# ---------------------------------------------------------------------------
# Simulink-schema (MATLAB physics-based) configuration
# ---------------------------------------------------------------------------
SIMULINK_SENSOR_COLS = [
    "N_meas", "Q_meas", "W_shaft_meas", "vib_NDE_X_meas",
    "bearing_T_meas", "lube_T_meas", "lube_P_meas", "lube_filter_dP_meas",
    "seal_dP_LP_meas", "seal_dP_HP_meas", "EGT_spread_meas",
    "SM_LP_meas", "SM_HP_meas", "PR_LP_meas", "T_out_LP_meas",
]

# ISA 5.1 / API 670 per-unit noise sigma (scales with UNIT_NOISE_SCALE)
SIMULINK_NOISE_SIGMA = {
    "N_meas":              2.0,
    "Q_meas":              25.4,
    "W_shaft_meas":        39_750.0,
    "vib_NDE_X_meas":      1.2,
    "bearing_T_meas":      0.5,
    "lube_T_meas":         0.5,
    "lube_P_meas":         0.005,
    "lube_filter_dP_meas": 0.005,
    "seal_dP_LP_meas":     0.005,
    "seal_dP_HP_meas":     0.005,
    "EGT_spread_meas":     0.5,
    "SM_LP_meas":          0.34,
    "SM_HP_meas":          0.45,
    "PR_LP_meas":          0.004,
    "T_out_LP_meas":       0.5,
}

SIMULINK_CLIPS = {
    "N_meas":              (8_000,   15_000),
    "Q_meas":              (0,       10_000),
    "W_shaft_meas":        (0,       12e6),
    "vib_NDE_X_meas":      (0,       200),
    "bearing_T_meas":      (20,      110),
    "lube_T_meas":         (20,      110),
    "lube_P_meas":         (0.1,     8.0),
    "lube_filter_dP_meas": (0,       2.0),
    "seal_dP_LP_meas":     (0,       10.0),
    "seal_dP_HP_meas":     (0,       10.0),
    "EGT_spread_meas":     (0,       60),
    "SM_LP_meas":          (-10,     70),
    "SM_HP_meas":          (-10,     70),
    "PR_LP_meas":          (1.0,     5.0),
    "T_out_LP_meas":       (50,      250),
}


# ---------------------------------------------------------------------------
# Step 1 — Load base dataset
# ---------------------------------------------------------------------------

def load_base(simulink_mode: bool = False,
              simulink_path: Path = None) -> pd.DataFrame:
    if simulink_mode:
        candidates = [
            simulink_path,
            Path("lp_simulink.parquet"),
            OUT / "lp_simulink.parquet",
        ]
        for p in candidates:
            if p and p.exists():
                df = pd.read_parquet(p)
                print(f"Base dataset (Simulink): {len(df):,} hours "
                      f"| {df.shape[1]} columns  <-- {p}")
                return df
        print("[ERROR] lp_simulink.parquet not found. "
              "Run Export_Dataset.m then Validate_Export.py first.")
        raise FileNotFoundError("lp_simulink.parquet not found")
    else:
        path = OUT / "lp_multiyear.parquet"
        if not path.exists():
            print("Base dataset not found -- running data_generator.py...")
            import subprocess
            subprocess.run(["python3", "data_generator.py"], check=True)
        df = pd.read_parquet(path)
        print(f"Base dataset (synthetic): {len(df):,} hours "
              f"| {df.shape[1]} columns")
        return df


# ---------------------------------------------------------------------------
# Step 2a — Per-unit noise (old synthetic schema)
# ---------------------------------------------------------------------------

def add_unit_noise(df: pd.DataFrame, unit_id: int) -> pd.DataFrame:
    rng   = np.random.default_rng(seed=unit_id * 1000 + 42)
    scale = UNIT_NOISE_SCALE[unit_id]
    out   = df.copy()
    noise_cfg = {
        "vib_NDE_X_um"          : (0.0, 0.8 * scale),
        "vib_NDE_Y_um"          : (0.0, 0.8 * scale),
        "vib_DE_X_um"           : (0.0, 0.9 * scale),
        "vib_DE_Y_um"           : (0.0, 0.9 * scale),
        "axial_disp_A_mm"       : (0.0, 0.002 * scale),
        "axial_disp_B_mm"       : (0.0, 0.002 * scale),
        "bearing_NDE_T_C"       : (0.0, 0.4 * scale),
        "bearing_DE_T_C"        : (0.0, 0.4 * scale),
        "poly_eta_realtime_pct" : (0.0, 0.2 * scale),
        "discharge_T_C"         : (0.0, 0.3 * scale),
        "inlet_P_bara"          : (0.0, 0.05 * scale),
        "lube_P_bara"           : (0.0, 0.04 * scale),
        "lube_filter_dP_bar"    : (0.0, 0.005 * scale),
        "seal_gas_LP_dP_bar"    : (0.0, 0.003 * scale),
    }
    for col, (mu, sigma) in noise_cfg.items():
        if col in out.columns:
            out[col] = (out[col] + rng.normal(mu, sigma, len(out))).astype(np.float32)
    out["vib_NDE_X_um"]   = out["vib_NDE_X_um"].clip(0, 80)
    out["vib_NDE_Y_um"]   = out["vib_NDE_Y_um"].clip(0, 80)
    out["bearing_NDE_T_C"]= out["bearing_NDE_T_C"].clip(30, 105)
    out["lube_P_bara"]    = out["lube_P_bara"].clip(0.5, 5.0)
    out["poly_eta_realtime_pct"] = out["poly_eta_realtime_pct"].clip(60, 92)
    return out


# ---------------------------------------------------------------------------
# Step 2b — Per-unit noise (simulink schema)
# ---------------------------------------------------------------------------

def add_unit_noise_simulink(df: pd.DataFrame, unit_id: int) -> pd.DataFrame:
    """Apply per-unit ISA 5.1 noise on top of MATLAB sensor-noise signals."""
    rng   = np.random.default_rng(seed=unit_id * 1000 + 99)
    scale = UNIT_NOISE_SCALE[unit_id]
    out   = df.copy()
    for col, sigma in SIMULINK_NOISE_SIGMA.items():
        if col not in out.columns:
            continue
        out[col] = out[col] + rng.normal(0, sigma * scale, len(out))
    for col, (lo, hi) in SIMULINK_CLIPS.items():
        if col in out.columns:
            out[col] = out[col].clip(lo, hi).astype(np.float32)
    if "fault_label" in out.columns:
        out["fault_label"] = out["fault_label"].astype(np.int32)
    return out


# ---------------------------------------------------------------------------
# Step 3 — Circular time shift
# ---------------------------------------------------------------------------

def circular_shift(df: pd.DataFrame, unit_id: int) -> pd.DataFrame:
    shift_h = (unit_id - 1) * UNIT_SHIFT_H
    n       = len(df)
    shift_h = shift_h % n
    vals_shifted = np.roll(df.values, -shift_h, axis=0)
    out = pd.DataFrame(vals_shifted, columns=df.columns)
    for col in ["fault_label"]:
        if col in out.columns:
            out[col] = out[col].astype(np.int32)
    for col in out.columns:
        if col not in ["fault_label", "timestamp"]:
            out[col] = out[col].astype(np.float32)
    out.index = pd.date_range("2024-01-01", periods=n, freq="1h")
    out.index.name = "timestamp"
    return out


# ---------------------------------------------------------------------------
# Step 4 — Generate all 15 units
# ---------------------------------------------------------------------------

def generate_fleet(simulink_mode: bool = False,
                   simulink_path: Path = None) -> dict:
    base  = load_base(simulink_mode, simulink_path)
    fleet = {}
    mode_tag = "Simulink" if simulink_mode else "Synthetic"
    print(f"\nGenerating fleet ({N_UNITS} units, "
          f"{SHIFT_MONTHS}-month circular shift, {mode_tag} base)...\n")

    for uid in range(1, N_UNITS + 1):
        shifted = circular_shift(base, uid)
        if simulink_mode:
            with_noise = add_unit_noise_simulink(shifted, uid)
        else:
            with_noise = add_unit_noise(shifted, uid)
        fleet[uid] = with_noise

        snap = with_noise.iloc[0]
        fl   = int(snap["fault_label"]) if "fault_label" in snap.index else -1
        rul  = float(snap["RUL"]) / 24 if "RUL" in snap.index else float(snap.get("rul_days", 0))
        vib  = float(snap.get("vib_NDE_X_meas",
                              snap.get("vib_NDE_X_um", 0)))
        state = {0: "HEALTHY ", 1: "WARNING ", 2: "FAULT   "}.get(fl, "?")
        print(f"  T{uid:02d}  shift={(uid-1)*SHIFT_MONTHS:2d}mo  "
              f"{state}  RUL={rul:5.1f}d  vib={vib:5.1f} um")

    return fleet


# ---------------------------------------------------------------------------
# Step 5 — Save
# ---------------------------------------------------------------------------

def save_fleet(fleet: dict, simulink_mode: bool = False) -> None:
    sub = "fleet_simulink" if simulink_mode else "fleet"
    fleet_dir = OUT / sub
    fleet_dir.mkdir(exist_ok=True)
    for uid, df in fleet.items():
        df.to_parquet(fleet_dir / f"unit_{uid:02d}.parquet")
    print(f"\nSaved {len(fleet)} unit files -> {fleet_dir}/")


def fleet_snapshot(fleet: dict) -> pd.DataFrame:
    rows = []
    for uid, df in fleet.items():
        snap = df.iloc[0]
        fl   = int(snap["fault_label"]) if "fault_label" in snap.index else -1
        rul  = float(snap["RUL"]) / 24 if "RUL" in snap.index else float(snap.get("rul_days", 0))
        vib  = float(snap.get("vib_NDE_X_meas",
                              snap.get("vib_NDE_X_um", 0)))
        rows.append({
            "unit_id":       uid,
            "tag":           f"Forouzan_SGT400_T{uid:02d}",
            "shift_months":  (uid - 1) * SHIFT_MONTHS,
            "fault_label":   fl,
            "status":        {0:"HEALTHY",1:"WARNING",2:"FAULT"}.get(fl, "?"),
            "rul_days":      round(rul, 1),
            "vib_NDE_X_um":  round(vib, 1),
        })
    return pd.DataFrame(rows).set_index("unit_id")


def print_fleet_summary(snapshot: pd.DataFrame) -> None:
    print("\n" + "=" * 70)
    print("  FLEET SNAPSHOT -- current state of all 15 units")
    print("=" * 70)
    healthy = (snapshot["fault_label"] == 0).sum()
    warning = (snapshot["fault_label"] == 1).sum()
    fault   = (snapshot["fault_label"] == 2).sum()
    print(f"\n  Healthy: {healthy}   Warning: {warning}   Fault: {fault}")
    print(f"  Average fleet RUL: {snapshot['rul_days'].mean():.0f} days\n")
    for uid, row in snapshot.iterrows():
        bar_len = int(min(row["rul_days"], 60) / 60 * 20)
        bar     = "█" * bar_len + "░" * (20 - bar_len)
        marker  = "!" if row["status"] == "WARNING" else ("X" if row["status"] == "FAULT" else " ")
        print(f"  T{uid:02d} {marker} [{bar}] "
              f"RUL={row['rul_days']:5.1f}d  "
              f"vib={row['vib_NDE_X_um']:5.1f} um  "
              f"{row['status']}")
    print("\n" + "=" * 70)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fleet generator for SGT-400 compressor units")
    parser.add_argument("--simulink", action="store_true",
                        help="Use MATLAB Simulink base dataset (lp_simulink.parquet)")
    parser.add_argument("--base", type=Path, default=None,
                        help="Path to base parquet file (overrides default path)")
    args = parser.parse_args()

    fleet    = generate_fleet(simulink_mode=args.simulink,
                              simulink_path=args.base)
    save_fleet(fleet, simulink_mode=args.simulink)
    snapshot = fleet_snapshot(fleet)
    print_fleet_summary(snapshot)

    out_dir = OUT / ("fleet_simulink" if args.simulink else "fleet")
    snapshot.to_csv(OUT / "fleet_snapshot.csv")
    print(f"\nFleet snapshot -> output/fleet_snapshot.csv")
    print(f"Unit parquets  -> {out_dir}/unit_01.parquet ... unit_15.parquet")
    print(f"\nTotal data: {N_UNITS} x {len(fleet[1]):,} hours = "
          f"{N_UNITS * len(fleet[1]):,} rows")
