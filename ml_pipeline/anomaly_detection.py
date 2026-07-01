"""
anomaly_detection.py
====================
Two complementary anomaly detection models for centrifugal compressor health.

Model 1 — Isolation Forest   : unsupervised multivariate outlier detection
Model 2 — LSTM Autoencoder   : learns normal patterns; flags deviations

Dataset: 3-year, 3 bearing-fault-cycle LP compressor data.
Training: healthy windows from all three inter-fault periods (combined).
Evaluation: per-fault-cycle so drift between cycles doesn't bias metrics.

References
----------
Liu et al. (2008)       — Isolation Forest
Malhotra et al. (2016)  — LSTM-based encoder-decoder for anomaly detection

Author : Amir Sarabandi
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, precision_recall_curve, auc
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import pickle, warnings
warnings.filterwarnings('ignore')

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
OUT    = Path("output")
OUT.mkdir(exist_ok=True)
print(f"Device: {DEVICE}")

# ─────────────────────────────────────────────────────────────────────────────
# 1. Load data
# ─────────────────────────────────────────────────────────────────────────────
print("\nLoading data...")
lp = pd.read_parquet(OUT / "lp_compressor.parquet")
print(f"  Dataset: {len(lp):,} samples | {lp.shape[1]} columns")
print(f"  Fault distribution: {dict(lp['fault_label'].value_counts().sort_index())}")

FEATURES = [
    "vib_NDE_X_um", "vib_NDE_Y_um", "vib_DE_X_um", "vib_DE_Y_um",
    "axial_disp_A_mm", "axial_disp_B_mm",
    "bearing_NDE_T_C", "bearing_DE_T_C",
    "poly_eta_realtime_pct", "discharge_T_C", "inlet_P_bara",
    "lube_P_bara", "lube_filter_dP_bar", "seal_gas_LP_dP_bar",
]

# ─────────────────────────────────────────────────────────────────────────────
# 2. Build training set — healthy windows from ALL inter-fault periods
# ─────────────────────────────────────────────────────────────────────────────
# Healthy = fault_label == 0, exclude the 30 days before each fault onset
# (those are "early warning" and could be borderline)

from data_generator import FAULT_CYCLES, N_HOURS

# Mark safe-healthy hours (label=0 and not within 30d of any fault)
safe_healthy = lp["fault_label"].values == 0
for fc in FAULT_CYCLES:
    fi = fc["fault_day"] * 24
    safe_healthy[max(0, fi - 30*24):fi] = False

X_all  = lp[FEATURES].values
y_all  = (lp["fault_label"].values > 0).astype(int)

X_train_raw = X_all[safe_healthy]
print(f"\n  Safe-healthy hours: {safe_healthy.sum():,} "
      f"({safe_healthy.sum()/len(lp)*100:.1f}% of dataset)")

scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train_raw)
X_all_s   = scaler.transform(X_all)

# ─────────────────────────────────────────────────────────────────────────────
# 3. Model 1 — Isolation Forest
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Isolation Forest ──────────────────────────────────────────")
iso = IsolationForest(n_estimators=300, contamination=0.05,
                      random_state=42, n_jobs=-1)
iso.fit(X_train_s)

iso_scores = -iso.score_samples(X_all_s)
iso_pred   = (iso.predict(X_all_s) == -1).astype(int)

roc_iso = roc_auc_score(y_all, iso_scores)
pr_p, pr_r, _ = precision_recall_curve(y_all, iso_scores)
pr_iso  = auc(pr_r, pr_p)

print(f"  ROC-AUC : {roc_iso:.3f}")
print(f"  PR-AUC  : {pr_iso:.3f}")
print(f"  Anomalies flagged: {iso_pred.sum():,} / {len(iso_pred):,}")

# Early detection per fault cycle
thr_iso = np.percentile(iso_scores[safe_healthy], 99)
for i, fc in enumerate(FAULT_CYCLES):
    fi = fc["fault_day"] * 24
    window = iso_scores[max(0,fi-60*24):fi]
    early  = np.where(window > thr_iso)[0]
    if len(early):
        days_early = (len(window) - early[0]) / 24
        print(f"  Fault {i+1}: detected {days_early:.0f} days before onset")
    else:
        print(f"  Fault {i+1}: not detected in 60-day pre-fault window")

# ─────────────────────────────────────────────────────────────────────────────
# 4. Model 2 — LSTM Autoencoder
# ─────────────────────────────────────────────────────────────────────────────
print("\n── LSTM Autoencoder ──────────────────────────────────────────")

SEQ_LEN = 24
BATCH   = 256
EPOCHS  = 40
LATENT  = 24

# Sequences from safe-healthy only
X_safe_s = X_all_s[safe_healthy]

def make_seqs(X, seq):
    return np.stack([X[i:i+seq] for i in range(len(X)-seq)]).astype(np.float32)

seqs_train = make_seqs(X_safe_s, SEQ_LEN)

# Full dataset sequences for evaluation
seqs_all = make_seqs(X_all_s, SEQ_LEN)
y_seq    = y_all[SEQ_LEN:][:len(seqs_all)]

loader = DataLoader(TensorDataset(torch.tensor(seqs_train)),
                    batch_size=BATCH, shuffle=True)

class LSTMAutoencoder(nn.Module):
    def __init__(self, n_feat, latent, seq_len):
        super().__init__()
        self.seq_len = seq_len
        self.enc = nn.LSTM(n_feat, latent, batch_first=True)
        self.dec = nn.LSTM(latent, n_feat, batch_first=True)
    def forward(self, x):
        _, (h, _) = self.enc(x)
        z = h[-1].unsqueeze(1).repeat(1, self.seq_len, 1)
        out, _ = self.dec(z)
        return out

n_feat = len(FEATURES)
model  = LSTMAutoencoder(n_feat, LATENT, SEQ_LEN).to(DEVICE)
optim  = torch.optim.Adam(model.parameters(), lr=1e-3)
loss_fn = nn.MSELoss()

print(f"  Training on {len(seqs_train):,} healthy sequences ({EPOCHS} epochs)...")
train_losses = []
for ep in range(EPOCHS):
    model.train(); el = 0
    for (xb,) in loader:
        xb = xb.to(DEVICE)
        loss = loss_fn(model(xb), xb)
        optim.zero_grad(); loss.backward(); optim.step()
        el += loss.item()
    train_losses.append(el / len(loader))
    if (ep+1) % 10 == 0:
        print(f"    Epoch {ep+1:02d}/{EPOCHS} — loss: {train_losses[-1]:.5f}")

# Reconstruction errors — full dataset
model.eval()
def get_errors(seqs):
    errs = []
    with torch.no_grad():
        for i in range(0, len(seqs), 512):
            xb   = torch.tensor(seqs[i:i+512]).to(DEVICE)
            pred = model(xb)
            errs.extend(((pred - xb)**2).mean(dim=(1,2)).cpu().numpy())
    return np.array(errs)

# Threshold from healthy reconstruction errors
train_errs = get_errors(seqs_train)
threshold  = np.percentile(train_errs, 99)
all_errs   = get_errors(seqs_all)
ae_pred    = (all_errs > threshold).astype(int)

roc_ae = roc_auc_score(y_seq, all_errs)
pr_p2, pr_r2, _ = precision_recall_curve(y_seq, all_errs)
pr_ae  = auc(pr_r2, pr_p2)

print(f"  Threshold (99th pct of healthy): {threshold:.5f}")
print(f"  ROC-AUC : {roc_ae:.3f}")
print(f"  PR-AUC  : {pr_ae:.3f}")
print(f"  Anomalies flagged: {ae_pred.sum():,} / {len(ae_pred):,}")

for i, fc in enumerate(FAULT_CYCLES):
    fi = fc["fault_day"] * 24 - SEQ_LEN
    window = all_errs[max(0,fi-60*24):fi]
    early  = np.where(window > threshold)[0]
    if len(early):
        days_early = (len(window) - early[0]) / 24
        print(f"  Fault {i+1}: detected {days_early:.0f} days before onset")
    else:
        print(f"  Fault {i+1}: not detected in 60-day pre-fault window")

# ─────────────────────────────────────────────────────────────────────────────
# 5. Dashboard
# ─────────────────────────────────────────────────────────────────────────────
print("\nGenerating results dashboard...")

hours = np.arange(len(lp))
days  = hours / 24

TC='#C9D1D9'; BG='#161B22'; GR='#21262D'
FC='#F85149'; WC='#E3B341'; AC='#58A6FF'; GC='#3FB950'
PURPLE='#8957E5'

fig = plt.figure(figsize=(16, 14), facecolor='#0D1117')
fig.suptitle(
    'LP Compressor — Anomaly Detection Results\n'
    'Isolation Forest vs LSTM Autoencoder | 3-year dataset | 3 bearing fault cycles',
    color='#E6EDF3', fontsize=13, fontweight='bold', y=0.98
)
gs = gridspec.GridSpec(3, 2, fig, hspace=0.48, wspace=0.32,
                        left=0.08, right=0.96, top=0.92, bottom=0.07)

def sax(ax, t):
    ax.set_facecolor(BG); ax.tick_params(colors=TC, labelsize=8)
    ax.set_title(t, color=TC, fontsize=9.5, pad=6, fontweight='semibold')
    ax.grid(True, color=GR, lw=0.5, ls='--', alpha=0.7)
    for sp in ax.spines.values(): sp.set_edgecolor('#30363D')
    ax.set_xlabel('Day', color=TC, fontsize=8)

# 1. Vibration NDE — 3 years
ax1 = fig.add_subplot(gs[0, 0])
sax(ax1, 'NDE Vibration — 3 years (VT-605-X)')
ax1.plot(days, lp["vib_NDE_X_um"].values, color=AC, lw=0.4, alpha=0.7)
ax1.axhline(50, color=WC, lw=1.2, ls='--', label='Alarm 50 µm')
ax1.axhline(75, color=FC, lw=1.2, ls='--', label='Trip 75 µm')
for i, fc in enumerate(FAULT_CYCLES):
    ax1.axvline(fc["fault_day"], color=PURPLE, lw=1.0, ls=':', alpha=0.8)
    ax1.text(fc["fault_day"]+3, 72, f'F{i+1}', color=PURPLE, fontsize=7)
ax1.set_ylabel('µm pk-pk', color=TC, fontsize=8)
ax1.legend(fontsize=7, facecolor=GR, labelcolor=TC, edgecolor='#30363D')
ax1.set_ylim(0, 88)

# 2. Isolation Forest score
ax2 = fig.add_subplot(gs[0, 1])
sax(ax2, 'Isolation Forest — anomaly score (3 years)')
ax2.plot(days, iso_scores, color=AC, lw=0.4, alpha=0.7)
ax2.axhline(thr_iso, color=WC, lw=1.2, ls='--', label='Threshold (99th pct)')
ax2.fill_between(days, iso_scores, thr_iso,
                  where=iso_scores > thr_iso, alpha=0.25, color=FC)
for i, fc in enumerate(FAULT_CYCLES):
    ax2.axvline(fc["fault_day"], color=PURPLE, lw=1.0, ls=':', alpha=0.8)
ax2.set_ylabel('Anomaly score', color=TC, fontsize=8)
ax2.legend(fontsize=7, facecolor=GR, labelcolor=TC, edgecolor='#30363D')

# 3. LSTM-AE reconstruction error
ae_days = days[SEQ_LEN:][:len(all_errs)]
ax3 = fig.add_subplot(gs[1, 0])
sax(ax3, 'LSTM Autoencoder — reconstruction error (3 years)')
ax3.plot(ae_days, all_errs, color=GC, lw=0.4, alpha=0.7)
ax3.axhline(threshold, color=WC, lw=1.2, ls='--', label='Threshold')
ax3.fill_between(ae_days, all_errs, threshold,
                  where=all_errs > threshold, alpha=0.25, color=FC)
for i, fc in enumerate(FAULT_CYCLES):
    ax3.axvline(fc["fault_day"], color=PURPLE, lw=1.0, ls=':', alpha=0.8)
ax3.set_ylabel('MSE reconstruction', color=TC, fontsize=8)
ax3.legend(fontsize=7, facecolor=GR, labelcolor=TC, edgecolor='#30363D')

# 4. Training loss
ax4 = fig.add_subplot(gs[1, 1])
sax(ax4, 'LSTM-AE training convergence')
ax4.plot(range(1, EPOCHS+1), train_losses, color=GC, lw=1.5, marker='o', ms=3)
ax4.set_xlabel('Epoch', color=TC, fontsize=8)
ax4.set_ylabel('MSE loss', color=TC, fontsize=8)

# 5. Model comparison
ax5 = fig.add_subplot(gs[2, 0])
sax(ax5, 'Model comparison — ROC-AUC & PR-AUC')
x = np.array([0, 1])
w = 0.30
b1 = ax5.bar(x-w/2, [roc_iso, roc_ae], w, color=AC, alpha=0.85, label='ROC-AUC')
b2 = ax5.bar(x+w/2, [pr_iso,  pr_ae],  w, color=GC, alpha=0.85, label='PR-AUC')
ax5.set_xticks(x)
ax5.set_xticklabels(['Isolation\nForest', 'LSTM\nAutoencoder'],
                     color=TC, fontsize=9)
ax5.set_ylim(0, 1.1)
ax5.set_ylabel('Score', color=TC, fontsize=8)
for bar in list(b1)+list(b2):
    ax5.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.02,
             f'{bar.get_height():.3f}', ha='center', color=TC, fontsize=8)
ax5.legend(fontsize=8, facecolor=GR, labelcolor=TC, edgecolor='#30363D')
ax5.set_xlabel('')

# 6. Summary
ax6 = fig.add_subplot(gs[2, 1])
ax6.set_facecolor(BG)
for sp in ax6.spines.values(): sp.set_edgecolor('#30363D')
ax6.set_xticks([]); ax6.set_yticks([])
lines = [
    ("ANOMALY DETECTION RESULTS",   '#E6EDF3', 11, True),
    ("",                            TC,  9, False),
    (f"Isolation Forest",           AC, 10, True),
    (f"  ROC-AUC  :  {roc_iso:.3f}", AC,  9, False),
    (f"  PR-AUC   :  {pr_iso:.3f}",  AC,  9, False),
    ("",                            TC,  9, False),
    (f"LSTM Autoencoder",           GC, 10, True),
    (f"  ROC-AUC  :  {roc_ae:.3f}", GC,  9, False),
    (f"  PR-AUC   :  {pr_ae:.3f}",  GC,  9, False),
    ("",                            TC,  9, False),
    ("Dataset: 3 yr | 3 fault cycles", '#8B949E', 8, False),
    ("Train:   healthy windows only",  '#8B949E', 8, False),
    ("Method:  unsupervised (no labels)", '#8B949E', 8, False),
]
y = 0.97
for txt, col, sz, bold in lines:
    ax6.text(0.05, y, txt, transform=ax6.transAxes, color=col, fontsize=sz,
             fontweight='bold' if bold else 'normal', fontfamily='monospace')
    y -= 0.085

fig.text(0.5, 0.005,
    'Both models trained on healthy data only — no fault labels used | '
    'API 670 alarm = 50 µm vibration threshold',
    ha='center', color='#8B949E', fontsize=7.5, style='italic')

plt.savefig(OUT / 'anomaly_detection_results.png',
            dpi=150, bbox_inches='tight', facecolor='#0D1117')

# Save artifacts
with open(OUT / "isolation_forest.pkl", "wb") as f:
    pickle.dump({"model": iso, "scaler": scaler,
                 "threshold": thr_iso, "features": FEATURES}, f)
torch.save({"model_state": model.state_dict(), "threshold": threshold,
            "scaler_mean": scaler.mean_, "scaler_std": scaler.scale_,
            "features": FEATURES, "seq_len": SEQ_LEN, "latent": LATENT}, 
           OUT / "lstm_autoencoder.pt")

print(f"Dashboard saved.")
print(f"\n{'='*50}")
print(f"  Isolation Forest  ROC-AUC: {roc_iso:.3f}  PR-AUC: {pr_iso:.3f}")
print(f"  LSTM Autoencoder  ROC-AUC: {roc_ae:.3f}  PR-AUC: {pr_ae:.3f}")
print(f"{'='*50}")
print("Done.")
