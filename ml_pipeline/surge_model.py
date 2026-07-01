"""
surge_model.py
==============
Physics-informed surge margin predictor for centrifugal compressors.

What is surge?
--------------
Surge is the most destructive instability in centrifugal compressors —
a violent reversal of flow that can destroy impellers, seals, and bearings
within seconds. Preventing it is the primary job of the anti-surge controller.

This model combines two approaches:
1. Physics baseline  : Greitzer (1976) B-parameter + Schultz polytropic method
   computes the theoretical surge margin from measured P, T, flow, speed.
2. ML correction     : Gradient Boosting learns the residual between the
   physics estimate and actual surge events (sensor drift, gas composition
   changes, fouling — things the physics model doesn't capture perfectly).

The combination is called a Physics-Informed Machine Learning (PIML) model.
It is more robust than pure ML (needs less data) and more accurate than
pure physics (adapts to real-world deviations).

Surge Margin definition used
-----------------------------
    SM = (Q_actual - Q_surge) / Q_surge × 100  (%)
    SM > 10%  → safe
    SM  5-10% → warning — anti-surge valve starts opening
    SM < 5%   → danger  — imminent surge

References
----------
Greitzer (1976)   — Surge and rotating stall in axial flow compressors
Schultz (1962)    — The polytropic analysis of centrifugal compressors
API 670 (2014)    — Machinery protection systems
Moore & Greitzer (1986) — A theory of post-stall transients in axial turbomachinery

Author : Amir Sarabandi
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
import pickle, warnings
warnings.filterwarnings('ignore')

OUT = Path("output")
OUT.mkdir(exist_ok=True)
np.random.seed(42)

print("Physics-Informed Surge Margin Predictor")
print("=" * 50)

# ─────────────────────────────────────────────────────────────────────────────
# 1. Design constants (from compressor_design_basis.py)
# ─────────────────────────────────────────────────────────────────────────────

LP = {
    "D1_mm"        : 335,       # first impeller diameter
    "N_design"     : 13000,     # rpm
    "Q_design"     : 8477,      # am³/hr — inlet volume flow at design
    "P_design"     : 17.5,      # bara — inlet
    "T_design"     : 28.9,      # °C
    "eta_design"   : 0.814,     # polytropic efficiency
    "n_poly"       : 1.31,      # polytropic exponent
    "MW"           : 21.9,      # gas molecular weight kg/kmol
    "R"            : 8314/21.9, # J/(kg·K)
    # Surge line coefficients (from performance map — Schultz method)
    # Q_surge = a0 + a1·N + a2·N² at test conditions
    "surge_a0"     : 3200.0,
    "surge_a1"     : 0.38,
    "surge_a2"     : -8e-6,
    # Stonewall (choke) coefficients
    "choke_a0"     : 6500.0,
    "choke_a1"     : 0.52,
    "choke_a2"     : -1.2e-5,
}

# ─────────────────────────────────────────────────────────────────────────────
# 2. Physics model — Schultz polytropic surge margin
# ─────────────────────────────────────────────────────────────────────────────

def flow_coefficient(Q_am3_hr, N_rpm, D_mm):
    """
    Dimensionless flow coefficient φ = Q / (N × D³)
    Q in m³/s, N in rev/s, D in m
    """
    Q_m3s = Q_am3_hr / 3600.0
    N_revs = N_rpm / 60.0
    D_m = D_mm / 1000.0
    return Q_m3s / (N_revs * D_m**3)

def head_coefficient(H_kJ_kg, N_rpm, D_mm):
    """Dimensionless head coefficient ψ = H / (N²·D²)"""
    N_revs = N_rpm / 60.0
    D_m = D_mm / 1000.0
    H_m2s2 = H_kJ_kg * 1000.0
    return H_m2s2 / ((N_revs * D_m)**2)

def polytropic_head(P_in, P_out, T_in, Z_mean, MW, n_p):
    """
    Schultz polytropic head (kJ/kg)
    H_p = (n_p/(n_p-1)) × Z_mean×R×T_in × [(P_out/P_in)^((n_p-1)/n_p) - 1]
    """
    R = 8314.0 / MW
    exponent = (n_p - 1.0) / n_p
    return (n_p / (n_p - 1.0)) * Z_mean * R * (T_in + 273.15) * \
           ((P_out / P_in) ** exponent - 1.0) / 1000.0

def surge_margin_physics(Q, N, P_in, P_out, T_in, lp=LP):
    """
    Compute surge margin (%) from measured operating point.
    Surge line from Schultz quadratic fit to performance map data.
    """
    # Surge flow at current speed (quadratic fit to speedlines)
    Q_surge = lp["surge_a0"] + lp["surge_a1"]*N + lp["surge_a2"]*N**2
    Q_surge = np.clip(Q_surge, 2000, 7000)

    # Speed correction: scale Q_surge to current inlet conditions
    # (similarity: Q ∝ N at constant density ratio)
    N_ratio = N / lp["N_design"]
    Q_surge_corrected = Q_surge * N_ratio

    SM = (Q - Q_surge_corrected) / Q_surge_corrected * 100.0
    return SM, Q_surge_corrected

# ─────────────────────────────────────────────────────────────────────────────
# 3. Generate realistic operating data with surge events
# ─────────────────────────────────────────────────────────────────────────────

print("\nGenerating operating data with surge events...")

N_HOURS = 3 * 365 * 24
rng     = np.random.default_rng(42)
t       = np.arange(N_HOURS)
t_yr    = t / 8760.0

# Normal operating band around design point
Q_op  = 8477 * (0.88 + 0.12 * np.sin(2*np.pi*t/8760))   # daily/seasonal variation
N_op  = 13000 * (0.93 + 0.05 * rng.normal(0, 1, N_HOURS)/10)
P_in  = 17.5 * np.exp(-0.07 * t_yr) + rng.normal(0, 0.05, N_HOURS)
P_out = 50.5 * (1 - 0.02 * t_yr) + rng.normal(0, 0.15, N_HOURS)
T_in  = 28.9 + 2.5 * t_yr + rng.normal(0, 0.1, N_HOURS)

Q_op  = np.clip(Q_op  + rng.normal(0, 80, N_HOURS),  4000, 10000).astype(np.float32)
N_op  = np.clip(N_op  + rng.normal(0, 50, N_HOURS),  9000, 14500).astype(np.float32)
P_in  = np.clip(P_in,  12.0, 22.0).astype(np.float32)
P_out = np.clip(P_out, 35.0, 60.0).astype(np.float32)
T_in  = np.clip(T_in,  20.0, 45.0).astype(np.float32)

# Gas composition drift (reservoir aging → MW increases slightly)
MW_op = 21.9 + 1.5 * t_yr + rng.normal(0, 0.2, N_HOURS)
MW_op = np.clip(MW_op, 20.0, 24.5).astype(np.float32)

# Fouling: efficiency degrades → effective surge line shifts inward by up to 5%
fouling_factor = 1.0 - 0.05 * (1 - np.exp(-0.008 * t_yr * 365))

# Inject 6 surge approach events (load reductions, start-ups, upsets)
SURGE_EVENTS = [
    {"h": 300*24,  "duration_h": 4,  "Q_drop_pct": 0.25},
    {"h": 710*24,  "duration_h": 6,  "Q_drop_pct": 0.30},
    {"h": 1050*24, "duration_h": 3,  "Q_drop_pct": 0.22},
    {"h": 1380*24, "duration_h": 8,  "Q_drop_pct": 0.28},
    {"h": 1820*24, "duration_h": 5,  "Q_drop_pct": 0.20},
    {"h": 2190*24, "duration_h": 4,  "Q_drop_pct": 0.35},
]

surge_label = np.zeros(N_HOURS, dtype=np.int8)
for ev in SURGE_EVENTS:
    hi = ev["h"]
    hf = min(hi + ev["duration_h"], N_HOURS)
    if hi >= N_HOURS: continue
    # Ramp Q down
    ramp = np.linspace(1.0, 1.0 - ev["Q_drop_pct"], hf - hi)
    Q_op[hi:hf] *= ramp
    surge_label[hi:hf] = 1   # surge approach

Q_op = np.clip(Q_op, 3000, 10000).astype(np.float32)

# ─────────────────────────────────────────────────────────────────────────────
# 4. Compute physics-based surge margin
# ─────────────────────────────────────────────────────────────────────────────

print("Computing physics-based surge margins...")
SM_physics = np.zeros(N_HOURS, dtype=np.float32)
Q_surge_line = np.zeros(N_HOURS, dtype=np.float32)

for i in range(N_HOURS):
    sm, qs = surge_margin_physics(Q_op[i], N_op[i], P_in[i], P_out[i], T_in[i])
    # Apply fouling correction (surge line shifts inward)
    sm_corrected = sm * fouling_factor[i]
    SM_physics[i]    = sm_corrected
    Q_surge_line[i]  = qs

SM_physics = np.clip(SM_physics, -30, 60).astype(np.float32)

# ─────────────────────────────────────────────────────────────────────────────
# 5. ML correction — Gradient Boosting learns residual
# ─────────────────────────────────────────────────────────────────────────────

print("Training ML correction model (Gradient Boosting)...")

# True SM (what we want to predict) = physics + sensor drift correction
# Simulate "true" SM with additional effects the physics model misses:
# - Gas composition effect on surge line
# - Anti-surge valve position feedback
# - Ambient temperature effect on density
ASV_pos = np.clip(20 - SM_physics * 1.5 + rng.normal(0, 3, N_HOURS), 0, 100)  # %
SM_true  = SM_physics \
           - 1.2 * (MW_op - 21.9)          \
           + 0.8 * (T_in - 28.9) / 10.0    \
           - 0.3 * (ASV_pos / 100.0)        \
           + rng.normal(0, 1.5, N_HOURS)
SM_true  = np.clip(SM_true, -30, 60).astype(np.float32)

# Features for ML
FEATURES_SURGE = [
    "SM_physics", "Q_am3_hr", "N_rpm", "P_in_bara", "P_out_bara",
    "T_in_C", "MW_kg_kmol", "ASV_position_pct",
    "pressure_ratio", "flow_coeff",
]

phi = np.array([flow_coefficient(Q_op[i], N_op[i], LP["D1_mm"])
                for i in range(N_HOURS)], dtype=np.float32)

df_surge = pd.DataFrame({
    "SM_physics"       : SM_physics,
    "Q_am3_hr"         : Q_op,
    "N_rpm"            : N_op,
    "P_in_bara"        : P_in,
    "P_out_bara"       : P_out,
    "T_in_C"           : T_in,
    "MW_kg_kmol"       : MW_op,
    "ASV_position_pct" : ASV_pos,
    "pressure_ratio"   : P_out / P_in,
    "flow_coeff"       : phi,
    "SM_true"          : SM_true,
    "surge_event"      : surge_label,
})

X = df_surge[FEATURES_SURGE].values
y = df_surge["SM_true"].values

X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25,
                                            random_state=42, shuffle=False)

scaler_s = StandardScaler()
X_tr_s   = scaler_s.fit_transform(X_tr)
X_te_s   = scaler_s.transform(X_te)

gb = GradientBoostingRegressor(
    n_estimators=200, max_depth=5, learning_rate=0.05,
    subsample=0.8, random_state=42
)
gb.fit(X_tr_s, y_tr)

y_pred   = gb.predict(X_te_s)
mae_s    = mean_absolute_error(y_te, y_pred)
r2_s     = r2_score(y_te, y_pred)
mae_phys = mean_absolute_error(y_te, X_te[:, 0])   # physics alone

print(f"  Physics-only MAE : {mae_phys:.2f}%")
print(f"  PIML model MAE   : {mae_s:.2f}%  (R² = {r2_s:.3f})")
print(f"  Improvement      : {(mae_phys-mae_s)/mae_phys*100:.1f}%")

# Danger zone detection (SM < 5%)
y_danger      = (y_te < 5).astype(int)
pred_danger   = (y_pred < 5).astype(int)
tp = ((y_danger==1)&(pred_danger==1)).sum()
fp = ((y_danger==0)&(pred_danger==1)).sum()
fn = ((y_danger==1)&(pred_danger==0)).sum()
precision = tp/(tp+fp) if tp+fp else 0
recall    = tp/(tp+fn) if tp+fn else 0
print(f"  Surge danger zone (SM<5%) — Precision:{precision:.2f} Recall:{recall:.2f}")

# Feature importance
feat_imp = pd.Series(gb.feature_importances_, index=FEATURES_SURGE)
print("\n  Top features:")
for f, imp in feat_imp.sort_values(ascending=False).head(5).items():
    print(f"    {f:30s} {imp:.3f}")

# ─────────────────────────────────────────────────────────────────────────────
# 6. Dashboard
# ─────────────────────────────────────────────────────────────────────────────

print("\nGenerating dashboard...")
days_all = np.arange(N_HOURS) / 24
# Downsample to daily for plotting
step = 24
d_plot  = days_all[::step]
sm_phys = SM_physics[::step]
sm_true = SM_true[::step]

# Full predictions
SM_pred_all = np.zeros(N_HOURS, dtype=np.float32)
X_all_s     = scaler_s.transform(df_surge[FEATURES_SURGE].values)
SM_pred_all = gb.predict(X_all_s).astype(np.float32)
sm_pred = SM_pred_all[::step]

TC='#C9D1D9'; BG='#161B22'; GR='#21262D'
FC='#F85149'; WC='#E3B341'; AC='#58A6FF'; GC='#3FB950'; PU='#8957E5'

fig = plt.figure(figsize=(16, 13), facecolor='#0D1117')
fig.suptitle(
    'LP Compressor — Surge Margin Prediction\n'
    'Physics-Informed ML (Greitzer + Gradient Boosting) | Persian Gulf Offshore',
    color='#E6EDF3', fontsize=13, fontweight='bold', y=0.98
)
gs = gridspec.GridSpec(3, 2, fig, hspace=0.48, wspace=0.32,
                        left=0.08, right=0.96, top=0.92, bottom=0.07)

def sax(ax, t):
    ax.set_facecolor(BG); ax.tick_params(colors=TC, labelsize=8)
    ax.set_title(t, color=TC, fontsize=9.5, pad=6, fontweight='semibold')
    ax.grid(True, color=GR, lw=0.5, ls='--', alpha=0.7)
    for sp in ax.spines.values(): sp.set_edgecolor('#30363D')

# 1. Surge margin — 3 years
ax1 = fig.add_subplot(gs[0, :])
sax(ax1, 'Surge Margin — 3 years | Physics baseline vs PIML prediction')
ax1.plot(d_plot, sm_true, color='#8B949E', lw=0.5, alpha=0.6, label='True SM')
ax1.plot(d_plot, sm_phys, color=AC, lw=0.6, alpha=0.7, label='Physics only')
ax1.plot(d_plot, sm_pred, color=GC, lw=0.7, alpha=0.85, label='PIML prediction')
ax1.axhline(10, color=WC, lw=1.5, ls='--', label='Warning (10%)')
ax1.axhline(5,  color=FC, lw=1.5, ls='--', label='Danger (5%)')
ax1.axhline(0,  color=FC, lw=1.0, ls=':',  alpha=0.5)
for ev in SURGE_EVENTS:
    ax1.axvspan(ev["h"]/24, (ev["h"]+ev["duration_h"])/24,
                alpha=0.2, color=FC, label='_')
ax1.text(SURGE_EVENTS[0]["h"]/24+1, -12, 'Surge\nevents',
         color=FC, fontsize=7)
ax1.set_xlabel('Day', color=TC, fontsize=8)
ax1.set_ylabel('Surge margin (%)', color=TC, fontsize=8)
ax1.legend(fontsize=7.5, facecolor=GR, labelcolor=TC,
           edgecolor='#30363D', loc='upper right', ncol=3)
ax1.set_ylim(-25, 65)

# 2. Scatter: physics vs PIML
ax2 = fig.add_subplot(gs[1, 0])
sax(ax2, 'PIML vs physics-only accuracy')
lims = [-20, 55]
ax2.scatter(y_te[::10], X_te[::10, 0], c='#8B949E', s=2,
            alpha=0.3, label='Physics only')
ax2.scatter(y_te[::10], y_pred[::10],  c=GC, s=2,
            alpha=0.4, label='PIML')
ax2.plot(lims, lims, color='white', lw=1, ls='--', alpha=0.5)
ax2.set_xlabel('True surge margin (%)', color=TC, fontsize=8)
ax2.set_ylabel('Predicted SM (%)', color=TC, fontsize=8)
ax2.legend(fontsize=7.5, facecolor=GR, labelcolor=TC, edgecolor='#30363D')
ax2.set_xlim(*lims); ax2.set_ylim(*lims)

# 3. Feature importance
ax3 = fig.add_subplot(gs[1, 1])
sax(ax3, 'Feature importance (Gradient Boosting)')
fi_sorted = feat_imp.sort_values()
colors_fi = [GC if v > 0.1 else AC for v in fi_sorted]
ax3.barh(range(len(fi_sorted)), fi_sorted.values, color=colors_fi, alpha=0.85)
ax3.set_yticks(range(len(fi_sorted)))
ax3.set_yticklabels(fi_sorted.index, color=TC, fontsize=7.5)
ax3.set_xlabel('Importance', color=TC, fontsize=8)
ax3.tick_params(colors=TC)

# 4. Surge event zoom
ax4 = fig.add_subplot(gs[2, 0])
sax(ax4, 'Surge event zoom — day 299–308')
ev1 = SURGE_EVENTS[0]
zoom_start = (ev1["h"] - 24) * 1
zoom_end   = (ev1["h"] + ev1["duration_h"] + 48) * 1
zh = np.arange(zoom_start, min(zoom_end, N_HOURS))
ax4.plot(zh/24, SM_true[zoom_start:zoom_end],
         color='#8B949E', lw=1.0, alpha=0.7, label='True SM')
ax4.plot(zh/24, SM_pred_all[zoom_start:zoom_end],
         color=GC, lw=1.2, alpha=0.9, label='PIML prediction')
ax4.axhline(10, color=WC, lw=1.2, ls='--')
ax4.axhline(5,  color=FC, lw=1.2, ls='--')
ax4.axvspan(ev1["h"]/24, (ev1["h"]+ev1["duration_h"])/24,
            alpha=0.2, color=FC)
ax4.set_xlabel('Day', color=TC, fontsize=8)
ax4.set_ylabel('Surge margin (%)', color=TC, fontsize=8)
ax4.legend(fontsize=7.5, facecolor=GR, labelcolor=TC, edgecolor='#30363D')

# 5. Summary
ax5 = fig.add_subplot(gs[2, 1])
ax5.set_facecolor(BG)
for sp in ax5.spines.values(): sp.set_edgecolor('#30363D')
ax5.set_xticks([]); ax5.set_yticks([])
lines = [
    ("SURGE MODEL — RESULTS",         '#E6EDF3', 11, True),
    ("",                               TC,  9, False),
    ("Physics baseline (Schultz/Greitzer)",  AC, 9, True),
    (f"  MAE      : {mae_phys:.2f}%",  AC,  9, False),
    ("",                               TC,  9, False),
    ("Physics-Informed ML (PIML)",     GC,  9, True),
    (f"  MAE      : {mae_s:.2f}%",     GC,  9, False),
    (f"  R²       : {r2_s:.3f}",       GC,  9, False),
    (f"  Improvement: {(mae_phys-mae_s)/mae_phys*100:.0f}% over physics", GC, 9, False),
    ("",                               TC,  9, False),
    ("Danger zone detection (SM<5%)",  WC,  9, True),
    (f"  Precision: {precision:.2f}",  WC,  9, False),
    (f"  Recall   : {recall:.2f}",     WC,  9, False),
    ("",                               TC,  9, False),
    ("6 surge events | 3-year dataset",  '#8B949E', 8, False),
    ("Method: Greitzer B-param + GB",    '#8B949E', 8, False),
]
y = 0.97
for txt, col, sz, bold in lines:
    ax5.text(0.05, y, txt, transform=ax5.transAxes, color=col, fontsize=sz,
             fontweight='bold' if bold else 'normal', fontfamily='monospace')
    y -= 0.075

fig.text(0.5, 0.005,
    'Physics: Greitzer (1976) + Schultz (1962) | '
    'ML: Gradient Boosting correction | API 670 thresholds',
    ha='center', color='#8B949E', fontsize=7.5, style='italic')

plt.savefig(OUT / 'surge_model_results.png',
            dpi=150, bbox_inches='tight', facecolor='#0D1117')

with open(OUT / "surge_model.pkl", "wb") as f:
    pickle.dump({"model": gb, "scaler": scaler_s,
                 "features": FEATURES_SURGE,
                 "mae": mae_s, "r2": r2_s,
                 "mae_physics": mae_phys}, f)

print(f"\n{'='*50}")
print(f"  Physics MAE  : {mae_phys:.2f}%")
print(f"  PIML MAE     : {mae_s:.2f}%")
print(f"  R²           : {r2_s:.3f}")
print(f"  Improvement  : {(mae_phys-mae_s)/mae_phys*100:.0f}%")
print(f"  Precision    : {precision:.2f}")
print(f"  Recall       : {recall:.2f}")
print(f"{'='*50}")
print("Done.")
