"""
rul_lstm.py
===========
Remaining Useful Life (RUL) prediction for centrifugal compressor bearings
using a supervised LSTM regression model.

RUL definition used here
------------------------
RUL = days until vibration reaches API 670 Zone C boundary (50 um alarm).
Pre-computed for all 3 fault cycles by data_generator.py and stored in
the rul_days column of lp_compressor.parquet. Capped at MAX_RUL = 60 days.

Author : Amir Sarabandi
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
warnings.filterwarnings('ignore')

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
OUT    = Path("output")
torch.manual_seed(42)
np.random.seed(42)
print(f"Device: {DEVICE}")

# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------
print("\nLoading data...")
lp = pd.read_parquet(OUT / "lp_compressor.parquet")

FEATURES = [
    "vib_NDE_X_um", "vib_NDE_Y_um", "vib_DE_X_um", "vib_DE_Y_um",
    "axial_disp_A_mm", "axial_disp_B_mm",
    "bearing_NDE_T_C", "bearing_DE_T_C",
    "poly_eta_realtime_pct", "discharge_T_C", "inlet_P_bara",
    "lube_P_bara", "lube_filter_dP_bar", "seal_gas_LP_dP_bar",
]

lp_h = lp[FEATURES + ["fault_label", "rul_days"]].resample("1h").mean()
lp_h["fault_label"] = lp[["fault_label"]].resample("1h").max()
n = len(lp_h)

print(f"  Dataset: {n:,} hourly samples | {lp_h['fault_label'].value_counts().to_dict()}")

# ---------------------------------------------------------------------------
# 2. Build RUL label  (all 3 fault cycles)
# ---------------------------------------------------------------------------
# Use the pre-computed rul_days from data_generator.py which correctly
# accounts for all three bearing fault cycles. The single-alarm approach
# (alarm_hours[0]) only covers cycle 1 and leaves cycles 2 & 3 with
# incorrect (negative) RUL values, starving the model of those examples.
MAX_RUL = 60

rul = lp_h["rul_days"].values.astype(np.float32)

print(f"  RUL range  : {rul.min():.1f} - {rul.max():.1f} days")
print(f"  RUL < 30 d : {(rul < 30).sum():,} samples  "
      f"({(rul < 30).sum() / n * 100:.1f}% of dataset)")
print(f"  RUL == 0 d : {(rul == 0).sum():,} samples  (at or past alarm)")

# Keep first-cycle alarm day for dashboard display only
ALARM_THRESHOLD = 50.0
vib = lp_h["vib_NDE_X_um"].values
alarm_hours_all = np.where(vib >= ALARM_THRESHOLD)[0]
alarm_hour = int(alarm_hours_all[0]) if len(alarm_hours_all) else \
             int(np.where(lp_h["fault_label"].values >= 2)[0][0])
alarm_day  = alarm_hour / 24
print(f"  First API 670 alarm: hour {alarm_hour} (day {alarm_day:.1f})")

# ---------------------------------------------------------------------------
# 3. Sequences
# ---------------------------------------------------------------------------
SEQ_LEN = 24

X_raw = lp_h[FEATURES].values.astype(np.float32)

# Train: days 0-310  |  Test: days 310-end
TRAIN_END = 310 * 24
scaler = StandardScaler()
scaler.fit(X_raw[:TRAIN_END])
X_s = scaler.transform(X_raw)

def make_xy(X, y, seq_len):
    xs, ys = [], []
    for i in range(len(X) - seq_len):
        xs.append(X[i:i+seq_len])
        ys.append(y[i + seq_len - 1])
    return np.array(xs, np.float32), np.array(ys, np.float32)

X_seq, y_seq = make_xy(X_s, rul, SEQ_LEN)
split = TRAIN_END - SEQ_LEN

X_tr, y_tr = X_seq[:split], y_seq[:split]
X_te, y_te = X_seq[split:], y_seq[split:]

print(f"  Train: {len(X_tr):,}  |  Test: {len(X_te):,}")
print(f"  Train RUL range: {y_tr.min():.1f} - {y_tr.max():.1f} days")
print(f"  Test  RUL range: {y_te.min():.1f} - {y_te.max():.1f} days")

loader_tr = DataLoader(TensorDataset(torch.tensor(X_tr),
                                      torch.tensor(y_tr).unsqueeze(1)),
                        batch_size=256, shuffle=True)
loader_te = DataLoader(TensorDataset(torch.tensor(X_te),
                                      torch.tensor(y_te).unsqueeze(1)),
                        batch_size=512)

# ---------------------------------------------------------------------------
# 4. Model
# ---------------------------------------------------------------------------
class RUL_LSTM(nn.Module):
    def __init__(self, n_feat, hidden=64, n_layers=2, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(n_feat, hidden, n_layers,
                             batch_first=True,
                             dropout=dropout if n_layers > 1 else 0)
        self.head = nn.Sequential(
            nn.Linear(hidden, 32), nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1), nn.ReLU()   # RUL >= 0
        )
    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :])

n_feat = len(FEATURES)
model  = RUL_LSTM(n_feat).to(DEVICE)
optim  = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
sched  = torch.optim.lr_scheduler.ReduceLROnPlateau(optim, patience=5, factor=0.5)
loss_fn = nn.HuberLoss(delta=5.0)

# ---------------------------------------------------------------------------
# 5. Train
# ---------------------------------------------------------------------------
EPOCHS = 60
print(f"\nTraining ({EPOCHS} epochs)...")
tr_losses, val_losses = [], []
best_val, best_state  = 1e9, None

for ep in range(EPOCHS):
    model.train(); tl = 0
    for xb, yb in loader_tr:
        xb, yb = xb.to(DEVICE), yb.to(DEVICE)
        loss = loss_fn(model(xb), yb)
        optim.zero_grad(); loss.backward(); optim.step()
        tl += loss.item()
    tl /= len(loader_tr)

    model.eval(); vl = 0
    with torch.no_grad():
        for xb, yb in loader_te:
            vl += loss_fn(model(xb.to(DEVICE)), yb.to(DEVICE)).item()
    vl /= len(loader_te)

    tr_losses.append(tl); val_losses.append(vl)
    sched.step(vl)

    if vl < best_val:
        best_val = vl
        best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    if (ep+1) % 10 == 0:
        print(f"  Ep {ep+1:02d}/{EPOCHS}  train:{tl:.3f}  val:{vl:.3f}")

model.load_state_dict(best_state)

# ---------------------------------------------------------------------------
# 6. Evaluate
# ---------------------------------------------------------------------------
model.eval()
preds = []
with torch.no_grad():
    for xb, _ in loader_te:
        preds.extend(model(xb.to(DEVICE)).cpu().numpy().flatten())
preds = np.array(preds)
trues = y_te

mae  = mean_absolute_error(trues, preds)
rmse = np.sqrt(mean_squared_error(trues, preds))

# PHM 2008 asymmetric score (penalises late predictions more than early)
d = preds - trues
phm = np.where(d < 0, np.exp(-d/13)-1, np.exp(d/10)-1).mean()

print(f"\n  MAE       : {mae:.2f} days")
print(f"  RMSE      : {rmse:.2f} days")
print(f"  PHM Score : {phm:.3f}  (< 1.0 = excellent)")

# Full-timeline predictions
full_preds = []
model.eval()
with torch.no_grad():
    for i in range(0, len(X_seq), 512):
        xb = torch.tensor(X_seq[i:i+512]).to(DEVICE)
        full_preds.extend(model(xb).cpu().numpy().flatten())
full_preds = np.array(full_preds)

# When does model first predict RUL <= 30 days?
MAINT_WIN = 30
alert_idxs = np.where(full_preds <= MAINT_WIN)[0]
alert_day  = alert_idxs[0] / 24 if len(alert_idxs) else None

if alert_day is not None:
    lead = alarm_day - alert_day
    print(f"  Model alert (RUL<={MAINT_WIN}d): Day {alert_day:.1f}")
    print(f"  First API 670 alarm:           Day {alarm_day:.1f}")
    print(f"  Lead time:                     {lead:.1f} days")

# ---------------------------------------------------------------------------
# 7. Dashboard
# ---------------------------------------------------------------------------
print("\nGenerating dashboard...")
all_days = np.arange(SEQ_LEN, n) / 24

fig = plt.figure(figsize=(16, 13), facecolor='#0D1117')
fig.suptitle(
    'LP Compressor -- Remaining Useful Life Prediction\n'
    'LSTM Regression | 3 bearing fault cycles | Persian Gulf Offshore',
    color='#E6EDF3', fontsize=13, fontweight='bold', y=0.98
)
gs = gridspec.GridSpec(3, 2, fig, hspace=0.48, wspace=0.32,
                        left=0.08, right=0.96, top=0.92, bottom=0.07)

TC='#C9D1D9'; BG='#161B22'; GR='#21262D'
FC='#F85149'; WC='#E3B341'; AC='#58A6FF'; GC='#3FB950'

def sax(ax, title):
    ax.set_facecolor(BG); ax.tick_params(colors=TC, labelsize=8)
    ax.set_title(title, color=TC, fontsize=9.5, pad=6, fontweight='semibold')
    ax.grid(True, color=GR, lw=0.5, ls='--', alpha=0.7)
    for sp in ax.spines.values(): sp.set_edgecolor('#30363D')

# 1. Full RUL timeline -- all 3 fault cycles visible
ax1 = fig.add_subplot(gs[0, :])
sax(ax1, 'Full timeline -- Actual RUL vs LSTM prediction (3 fault cycles)')
ax1.plot(all_days, y_seq[:len(all_days)], color='#8B949E',
         lw=1.0, alpha=0.8, label='Actual RUL')
ax1.plot(all_days, full_preds[:len(all_days)], color=AC,
         lw=1.0, alpha=0.85, label='Predicted RUL')
ax1.axhline(MAINT_WIN, color=WC, lw=1.5, ls='--',
            label=f'Maintenance trigger ({MAINT_WIN} d)')
ax1.axhline(0, color=FC, lw=1.0, ls='--', alpha=0.6, label='Alarm')
ax1.axvline(alarm_day, color=FC, lw=1.5, ls=':', alpha=0.9)
ax1.text(alarm_day+1, 52, f'API 670 alarm\nDay {alarm_day:.0f}',
         color=FC, fontsize=7.5)
if alert_day:
    ax1.axvline(alert_day, color=WC, lw=1.5, ls=':', alpha=0.9)
    ax1.text(alert_day+1, 38, f'Model alert\nDay {alert_day:.0f}',
             color=WC, fontsize=7.5)
ax1.axvspan(0, TRAIN_END/24, alpha=0.05, color=GC)
ax1.axvspan(TRAIN_END/24, all_days[-1], alpha=0.05, color=FC)
ax1.text(10, MAX_RUL-8, 'Training', color=GC, fontsize=8, alpha=0.7)
ax1.text(TRAIN_END/24+2, MAX_RUL-8, 'Test', color=FC, fontsize=8, alpha=0.7)
ax1.set_xlabel('Day of operation', color=TC, fontsize=8)
ax1.set_ylabel('RUL (days)', color=TC, fontsize=8)
ax1.legend(fontsize=7.5, facecolor=GR, labelcolor=TC,
           edgecolor='#30363D', loc='upper right', ncol=2)
ax1.set_ylim(-3, MAX_RUL+5)

# 2. Scatter predicted vs actual
ax2 = fig.add_subplot(gs[1, 0])
sax(ax2, 'Predicted vs actual RUL (test set)')
ax2.scatter(trues, preds, c=AC, s=3, alpha=0.4)
lm = [0, MAX_RUL]
ax2.plot(lm, lm, color='#8B949E', lw=1, ls='--', label='Perfect')
ax2.plot(lm, [l+10 for l in lm], color=WC, lw=0.8, ls=':', alpha=0.6)
ax2.plot(lm, [max(0,l-10) for l in lm], color=WC, lw=0.8, ls=':', alpha=0.6)
ax2.set_xlabel('Actual RUL (days)', color=TC, fontsize=8)
ax2.set_ylabel('Predicted RUL (days)', color=TC, fontsize=8)
ax2.legend(fontsize=7, facecolor=GR, labelcolor=TC, edgecolor='#30363D')
ax2.set_xlim(0, MAX_RUL); ax2.set_ylim(0, MAX_RUL)

# 3. Error histogram
ax3 = fig.add_subplot(gs[1, 1])
sax(ax3, 'Prediction error distribution')
res = preds - trues
ax3.hist(res, bins=40, color=AC, alpha=0.75, edgecolor='none')
ax3.axvline(0, color='#8B949E', lw=1, ls='--')
ax3.axvline(res.mean(), color=WC, lw=1.5, label=f'Mean {res.mean():.1f} d')
ax3.set_xlabel('Error (days)', color=TC, fontsize=8)
ax3.set_ylabel('Count', color=TC, fontsize=8)
ax3.legend(fontsize=7.5, facecolor=GR, labelcolor=TC, edgecolor='#30363D')

# 4. Training curve
ax4 = fig.add_subplot(gs[2, 0])
sax(ax4, 'Training convergence')
ax4.plot(range(1, EPOCHS+1), tr_losses, color=GC, lw=1.5, label='Train')
ax4.plot(range(1, EPOCHS+1), val_losses, color=AC, lw=1.5, label='Val')
ax4.set_xlabel('Epoch', color=TC, fontsize=8)
ax4.set_ylabel('Huber loss', color=TC, fontsize=8)
ax4.legend(fontsize=8, facecolor=GR, labelcolor=TC, edgecolor='#30363D')

# 5. Summary box
ax5 = fig.add_subplot(gs[2, 1])
ax5.set_facecolor(BG)
for sp in ax5.spines.values(): sp.set_edgecolor('#30363D')
ax5.set_xticks([]); ax5.set_yticks([])

adv = f"{alarm_day - alert_day:.0f}" if alert_day else "N/A"
lines = [
    ("RUL MODEL -- RESULTS",      '#E6EDF3', 11, True),
    ("",                           TC, 9, False),
    (f"MAE         {mae:.1f} days",   GC, 10, False),
    (f"RMSE        {rmse:.1f} days",  GC, 10, False),
    (f"PHM Score   {phm:.3f}",        GC, 10, False),
    ("",                           TC, 9, False),
    (f"Model alert (RUL<=30d): Day {alert_day:.0f}" if alert_day
      else "No alert triggered",   WC, 9, False),
    (f"API 670 alarm (cycle 1): Day {alarm_day:.0f}", FC, 9, False),
    (f"Advance warning:       {adv} days", GC, 9, True),
    ("",                           TC, 9, False),
    ("Dataset: 3 yr | 3 fault cycles",     '#8B949E', 8, False),
    ("RUL label: all cycles (data_gen)",   '#8B949E', 8, False),
    ("Planned vs unplanned ~= 1:5 cost",   '#8B949E', 8, False),
]
y = 0.97
for txt, col, sz, bold in lines:
    ax5.text(0.05, y, txt, transform=ax5.transAxes,
             color=col, fontsize=sz,
             fontweight='bold' if bold else 'normal',
             fontfamily='monospace')
    y -= 0.082

fig.text(0.5, 0.005,
    'LSTM regression | Huber loss | 24-h sliding window | '
    'RUL pre-computed for all 3 fault cycles by data_generator.py',
    ha='center', color='#8B949E', fontsize=7.5, style='italic')

plt.savefig(OUT / 'rul_lstm_results.png',
            dpi=150, bbox_inches='tight', facecolor='#0D1117')

torch.save({
    "model_state": best_state,
    "scaler_mean": scaler.mean_, "scaler_std": scaler.scale_,
    "features": FEATURES, "seq_len": SEQ_LEN,
    "mae": mae, "rmse": rmse, "phm": phm,
}, OUT / "rul_lstm.pt")

print(f"\n{'='*52}")
print(f"  MAE       : {mae:.1f} days")
print(f"  RMSE      : {rmse:.1f} days")
print(f"  PHM Score : {phm:.3f}")
if alert_day:
    print(f"  Alert day : {alert_day:.0f}  ({alarm_day-alert_day:.0f} days before API 670 alarm)")
print(f"{'='*52}")
print("Done.")
