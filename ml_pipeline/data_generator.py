"""
data_generator.py
=================
Physics-informed synthetic time-series data generator for centrifugal
compressor predictive maintenance.

Generates a 3-year dataset with 3 bearing fault cycles of varying severity.
Multi-year / multi-fault data is essential for training robust ML models —
a single fault cycle gives too few degradation examples for generalization.

Design philosophy
-----------------
Every signal is anchored to a thermodynamic or mechanical first principle.
Degradation curves use published empirical models, not arbitrary ramps.

Degradation models used
-----------------------
- Fouling (efficiency loss)  : Tarabrin et al. (1998) — exponential decay
- Bearing wear (vibration)   : ISO 13373 / API 670 severity zones
- Lube oil filter clogging   : Darcy-Weisbach + cake filtration (Ruth 1935)
- Reservoir depletion        : Arps (1945) exponential decline

Dataset summary
---------------
Duration  : 3 years (26,280 hourly samples)
Faults    : 3 LP NDE bearing degradation cycles (day 300, 645, 1092)
Labels    : fault_label  (0=healthy, 1=early warning, 2=active fault)
            rul_days     (days to next API 670 alarm, capped at 60 d)

Author : Amir Sarabandi
Project: Offshore Gas Compressor Predictive Maintenance
"""

import numpy as np
import pandas as pd
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

N_YEARS      = 3
SAMPLE_HOURS = 1                          # 1-hour samples (fast + realistic)
N_HOURS      = N_YEARS * 365 * 24         # 26,280 hours
MAX_RUL      = 60                         # cap healthy-period RUL (days)
ALARM_VIB    = 50.0                       # API 670 Zone C boundary (µm)

# Three bearing fault cycles with different severity
FAULT_CYCLES = [
    {"fault_day": 300, "alarm_day": 342, "mag_vib": 38, "mag_T": 22},
    {"fault_day": 645, "alarm_day": 687, "mag_vib": 45, "mag_T": 26},
    {"fault_day": 992, "alarm_day": 1034,"mag_vib": 32, "mag_T": 18},
]

FEATURES = [
    "vib_NDE_X_um", "vib_NDE_Y_um", "vib_DE_X_um", "vib_DE_Y_um",
    "axial_disp_A_mm", "axial_disp_B_mm",
    "bearing_NDE_T_C", "bearing_DE_T_C",
    "poly_eta_realtime_pct", "discharge_T_C", "inlet_P_bara",
    "lube_P_bara", "lube_filter_dP_bar", "seal_gas_LP_dP_bar",
]


# ─────────────────────────────────────────────────────────────────────────────
# Signal builder
# ─────────────────────────────────────────────────────────────────────────────

def sig(rng, base, noise_pct, n, trend=0.0, clip_lo=None, clip_hi=None):
    """
    Base signal with measurement noise, annual seasonal variation,
    and linear drift (aging / reservoir depletion).
    """
    t = np.arange(n, dtype=np.float64)
    s = rng.normal(0, base * noise_pct / 100, n)
    s += base * 0.015 * np.sin(2 * np.pi * t / 8760)   # seasonal
    s += trend * t / n
    s += base
    if clip_lo is not None: s = np.clip(s, clip_lo, None)
    if clip_hi is not None: s = np.clip(s, None, clip_hi)
    return s.astype(np.float32)


def inject_faults(signal, fault_cycles, magnitude_key, exponent=1.8,
                  clip_lo=None, clip_hi=None):
    """Add accelerating ramp for each fault cycle (Weibull-like shape)."""
    s = signal.copy()
    for fc in fault_cycles:
        fi   = fc["fault_day"] * 24
        tail = len(s) - fi
        if tail <= 0:
            continue
        x = np.linspace(0, 1, tail) ** exponent
        s[fi:] += fc[magnitude_key] * x
    if clip_lo is not None: s = np.clip(s, clip_lo, None)
    if clip_hi is not None: s = np.clip(s, None, clip_hi)
    return s


# ─────────────────────────────────────────────────────────────────────────────
# LP Compressor — 3-year dataset
# ─────────────────────────────────────────────────────────────────────────────

def generate_lp(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n   = N_HOURS

    # ── Process signals ───────────────────────────────────────────────────────
    # Reservoir depletion (Arps exponential): P(t) = Pi·exp(−Di·t)
    t_yr       = np.linspace(0, N_YEARS, n)
    inlet_P_t  = 17.5 * np.exp(-0.07 * t_yr) - 17.5   # cumulative trend

    inlet_P    = sig(rng, 17.5, 0.30, n, trend=inlet_P_t[-1], clip_lo=14.0)
    inlet_T    = sig(rng, 28.9, 0.35, n, trend=+2.5)
    disch_P    = sig(rng, 50.5, 0.30, n, trend=-1.2)

    # Fouling: discharge temp rises as efficiency drops (Tarabrin 1998)
    fouling_dT = 3.5 * N_YEARS * (1 - np.exp(-0.008 * t_yr * 365))
    disch_T    = sig(rng, 116.0, 0.35, n, trend=fouling_dT[-1])
    mass_flow  = sig(rng, 136_684, 0.96, n, trend=-8_000, clip_lo=100_000)

    # Polytropic efficiency degradation (Tarabrin 1998)
    eta_loss   = 81.4 * 0.055 * N_YEARS * (1 - np.exp(-0.008 * t_yr * 365))
    poly_eta   = sig(rng, 81.4, 0.50, n, trend=-eta_loss[-1], clip_lo=72.0)

    power      = sig(rng, 6_100, 1.03, n, trend=+250.0)
    speed      = sig(rng, 13_000, 0.10, n)

    # ── Vibration + fault injection ───────────────────────────────────────────
    vib_nde_x  = inject_faults(
        sig(rng, 18.0, 5.0, n, clip_lo=0),
        FAULT_CYCLES, "mag_vib", clip_hi=80.0
    )
    vib_nde_y  = inject_faults(
        sig(rng, 18.0, 5.0, n, clip_lo=0),
        [{**fc, "mag_vib": fc["mag_vib"]*0.85} for fc in FAULT_CYCLES],
        "mag_vib", clip_hi=80.0
    )
    vib_de_x   = inject_faults(
        sig(rng, 20.0, 5.0, n, clip_lo=0),
        [{**fc, "mag_vib": fc["mag_vib"]*0.30} for fc in FAULT_CYCLES],
        "mag_vib", clip_hi=60.0
    )
    vib_de_y   = inject_faults(
        sig(rng, 20.0, 5.0, n, clip_lo=0),
        [{**fc, "mag_vib": fc["mag_vib"]*0.25} for fc in FAULT_CYCLES],
        "mag_vib", clip_hi=60.0
    )
    axial_a    = inject_faults(
        sig(rng, 0.05, 5.0, n, clip_lo=0),
        [{**fc, "mag_vib": 0.18} for fc in FAULT_CYCLES],
        "mag_vib", exponent=2.0, clip_hi=0.5
    )
    axial_b    = inject_faults(
        sig(rng, 0.04, 5.0, n, clip_lo=0),
        [{**fc, "mag_vib": 0.15} for fc in FAULT_CYCLES],
        "mag_vib", exponent=2.0, clip_hi=0.5
    )

    # ── Bearing temperatures ──────────────────────────────────────────────────
    bearing_NDE = inject_faults(
        sig(rng, 65.0, 0.50, n, trend=+2.0),
        FAULT_CYCLES, "mag_T", exponent=1.6, clip_hi=100.0
    )
    bearing_DE  = inject_faults(
        sig(rng, 68.0, 0.50, n, trend=+1.5),
        [{**fc, "mag_T": fc["mag_T"]*0.35} for fc in FAULT_CYCLES],
        "mag_T", exponent=1.5, clip_hi=100.0
    )

    # ── Lube oil — filter clogging (Ruth cake filtration) ────────────────────
    lube_P     = sig(rng, 2.8, 0.30, n, clip_lo=1.0)
    lube_T     = sig(rng, 48.0, 0.50, n, trend=+2.0)
    filter_dp  = sig(rng, 0.12, 2.0, n,
                      trend=0.35 * np.sqrt(N_YEARS), clip_lo=0)

    # ── Seal gas ──────────────────────────────────────────────────────────────
    sg_lp_dP   = sig(rng, 0.08, 3.0, n, clip_lo=0)

    # ── Derived: real-time polytropic efficiency ──────────────────────────────
    eta_rt = (1.31/0.31) * np.log(disch_P / inlet_P) / \
             np.log((disch_T + 273.15) / (inlet_T + 273.15))
    eta_rt = np.clip(eta_rt, 0.60, 0.90) * 100

    # ── Fault labels ──────────────────────────────────────────────────────────
    fault_label = np.zeros(n, dtype=np.int8)
    for fc in FAULT_CYCLES:
        fi      = fc["fault_day"] * 24
        warn_i  = max(0, fi - 14*24)      # 14-day early warning
        if fi < n:
            fault_label[warn_i:fi] = 1    # zone: early warning
        fault_label[fi:]           = 2    # zone: active fault
        # reset for next cycle (machine repaired between faults)
        repair_i = fc["alarm_day"] * 24 + 72    # 3-day repair window
        if repair_i < n:
            fault_label[repair_i:] = 0

    # ── RUL label — days to next API 670 alarm ────────────────────────────────
    rul = np.full(n, float(MAX_RUL), dtype=np.float32)
    for fc in FAULT_CYCLES:
        ai = fc["alarm_day"] * 24
        for h in range(max(0, ai - MAX_RUL*24), min(ai, n)):
            rul[h] = min(rul[h], (ai - h) / 24.0)
    rul = np.clip(rul, 0, MAX_RUL).astype(np.float32)

    # ── Assemble DataFrame ────────────────────────────────────────────────────
    idx = pd.date_range("2024-01-01", periods=n, freq="1h")
    df  = pd.DataFrame({
        "vib_NDE_X_um"          : vib_nde_x,
        "vib_NDE_Y_um"          : vib_nde_y,
        "vib_DE_X_um"           : vib_de_x,
        "vib_DE_Y_um"           : vib_de_y,
        "axial_disp_A_mm"       : axial_a,
        "axial_disp_B_mm"       : axial_b,
        "bearing_NDE_T_C"       : bearing_NDE,
        "bearing_DE_T_C"        : bearing_DE,
        "poly_eta_realtime_pct" : eta_rt.astype(np.float32),
        "discharge_T_C"         : disch_T,
        "inlet_P_bara"          : inlet_P,
        "lube_P_bara"           : lube_P,
        "lube_filter_dP_bar"    : filter_dp,
        "seal_gas_LP_dP_bar"    : sg_lp_dP,
        "fault_label"           : fault_label,
        "rul_days"              : rul,
    }, index=idx)
    df.index.name = "timestamp"
    return df


# ─────────────────────────────────────────────────────────────────────────────
# HP Compressor — 3-year dataset (healthy in this scenario)
# ─────────────────────────────────────────────────────────────────────────────

def generate_hp(seed: int = 99) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n   = N_HOURS
    t_yr = np.linspace(0, N_YEARS, n)

    eta_loss = 55.6 * 0.055 * N_YEARS * (1 - np.exp(-0.010 * t_yr * 365))

    idx = pd.date_range("2024-01-01", periods=n, freq="1h")
    df  = pd.DataFrame({
        "vib_NDE_X_um"          : sig(rng, 15.0, 5.0, n, clip_lo=0),
        "vib_NDE_Y_um"          : sig(rng, 15.0, 5.0, n, clip_lo=0),
        "vib_DE_X_um"           : sig(rng, 17.0, 5.0, n, clip_lo=0),
        "vib_DE_Y_um"           : sig(rng, 17.0, 5.0, n, clip_lo=0),
        "axial_disp_A_mm"       : sig(rng, 0.04, 5.0, n, clip_lo=0),
        "axial_disp_B_mm"       : sig(rng, 0.04, 5.0, n, clip_lo=0),
        "bearing_NDE_T_C"       : sig(rng, 72.0, 0.50, n, trend=+1.5),
        "bearing_DE_T_C"        : sig(rng, 75.0, 0.50, n, trend=+1.2),
        "poly_eta_realtime_pct" : sig(rng, 55.6, 0.50, n,
                                       trend=-eta_loss[-1], clip_lo=46.0),
        "discharge_T_C"         : sig(rng, 162.0, 0.35, n, trend=+4.5),
        "inlet_P_bara"          : sig(rng, 48.8,  0.30, n,
                                       trend=-3.5 * N_YEARS, clip_lo=42.0),
        "lube_P_bara"           : sig(rng, 2.8,   0.30, n, clip_lo=1.0),
        "lube_filter_dP_bar"    : sig(rng, 0.10,  2.0,  n,
                                       trend=0.28 * np.sqrt(N_YEARS), clip_lo=0),
        "seal_gas_HP_dP_bar"    : sig(rng, 0.10,  3.0,  n, clip_lo=0),
        "fault_label"           : np.zeros(n, dtype=np.int8),
        "rul_days"              : np.full(n, float(MAX_RUL), dtype=np.float32),
    }, index=idx)
    df.index.name = "timestamp"
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def generate(output_dir: str = "output") -> tuple:
    out = Path(output_dir)
    out.mkdir(exist_ok=True)

    print(f"Generating {N_YEARS}-year dataset  ({N_HOURS:,} hourly samples)...")
    print(f"Fault cycles: {len(FAULT_CYCLES)}  (LP NDE bearing, varying severity)")

    lp_df = generate_lp()
    hp_df = generate_hp()

    lp_df.to_parquet(out / "lp_compressor.parquet")
    hp_df.to_parquet(out / "hp_compressor.parquet")
    # Alias used by rul_lstm.py
    lp_df.to_parquet(out / "lp_multiyear.parquet")

    fl   = lp_df["fault_label"].value_counts().sort_index()
    print(f"\nLP dataset: {len(lp_df):,} samples | {len(lp_df.columns)} columns")
    print(f"  Fault labels  : {dict(fl)}")
    print(f"  RUL < 30 days : {(lp_df.rul_days < 30).sum():,} samples")
    print(f"  Max vib NDE   : {lp_df.vib_NDE_X_um.max():.1f} µm")
    print(f"  Poly η day-1  : {lp_df.poly_eta_realtime_pct.iloc[:24].mean():.1f}%  "
          f"→ day-{N_YEARS*365}: {lp_df.poly_eta_realtime_pct.iloc[-24:].mean():.1f}%")

    print(f"\nHP dataset: {len(hp_df):,} samples | healthy scenario")
    print(f"\nSaved to {out.resolve()}/")
    return lp_df, hp_df


if __name__ == "__main__":
    generate()
