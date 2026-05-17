#!/usr/bin/env python3
"""
Turing Reaction-Diffusion Simulation (Gray-Scott variant)
=========================================================
Runs the RD system on the spatial grid to produce rd_demand_pressure feature.
"""
import os
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("[1/4] Loading grid data...", BASE)
data = np.load(os.path.join(BASE, "data/gold/turing_rd_inputs.npz"))
A_init = data["A_norm"].copy()
B_init = data["B_norm"].copy()
grid_shape = tuple(data["grid_shape"])
lat_bins = data["lat_bins"]
lon_bins = data["lon_bins"]

n_lat, n_lon = grid_shape
print(f"  Grid: {n_lat} x {n_lon}")

# ── Gray-Scott Parameters ──────────────────────────────────────────
D_A = 0.16    # Demand diffusion (slow  demand doesn't spread easily)
D_B = 0.08    # Saturation diffusion (fast  competition spreads)
F = 0.035     # Feed rate
k = 0.065     # Kill rate
dt = 1.0      # Time step
T = 500       # Iterations (reduced from 1000 for speed; sufficient for convergence)

# ── Create a land mask (only simulate where outlets exist) ─────────
# Dilate the occupied cells by 5 cells to allow diffusion
from scipy.ndimage import binary_dilation, laplace
occupied = (A_init > 0) | (B_init > 0)
land_mask = binary_dilation(occupied, iterations=5)
print(f"  Active cells in mask: {land_mask.sum()} / {n_lat * n_lon}")

# ── Initialize fields ─────────────────────────────────────────────
# A starts from demand data, B starts from density data
# Add small random perturbation to break symmetry
rng = np.random.default_rng(42)
A = A_init.copy()
B = B_init.copy()

# Where there's no data, set baseline values for RD dynamics
A[~occupied] = 0.0
B[~occupied] = 0.0

# Ensure minimum values in occupied cells for RD to work
A[occupied & (A == 0)] = 0.01
B[occupied & (B == 0)] = 0.01

print(f"\n[2/4] Running Gray-Scott RD simulation ({T} steps)...")
for t in range(T):
    # Laplacians (discrete approximation)
    lap_A = laplace(A)
    lap_B = laplace(B)
    
    # Gray-Scott equations
    AB2 = A * A * B
    dA = D_A * lap_A - AB2 + F * (1.0 - A)
    dB = D_B * lap_B + AB2 - (F + k) * B
    
    A += dt * dA
    B += dt * dB
    
    # Clamp to [0, 1]
    A = np.clip(A, 0, 1)
    B = np.clip(B, 0, 1)
    
    # Only update within land mask
    A[~land_mask] = 0
    B[~land_mask] = 0
    
    if (t + 1) % 100 == 0:
        print(f"  Step {t+1}/{T}  A range: [{A.min():.4f}, {A.max():.4f}], "
              f"B range: [{B.min():.4f}, {B.max():.4f}]")

print(f"\n[3/4] Extracting steady-state features...")
# The steady-state A field = demand pressure surface
# High A = demand hotspot, Low A = saturated/isolated
A_steady = A.copy()

# Save the RD grid
np.savez(
    os.path.join(BASE, "data/gold/rd_grid.npz"),
    A_steady=A_steady, B_steady=B, A_init=A_init, B_init=B_init,
    lat_bins=lat_bins, lon_bins=lon_bins, grid_shape=np.array(grid_shape)
)

# Map back to outlets
outlet_feats = pd.read_parquet(os.path.join(BASE, "data/gold/turing_outlet_features.parquet"))
print(f"  Mapping RD values to {len(outlet_feats)} outlets...")

rd_values = []
for _, row in outlet_feats.iterrows():
    i, j = int(row["lat_bin"]), int(row["lon_bin"])
    if 0 <= i < n_lat and 0 <= j < n_lon:
        rd_values.append(A_steady[i, j])
    else:
        rd_values.append(0.0)

outlet_feats["rd_demand_pressure"] = rd_values

# Save enriched features
outlet_feats.to_parquet(
    os.path.join(BASE, "data/gold/turing_outlet_features.parquet"), index=False
)

# ── Visualize RD results ───────────────────────────────────────────
print("[4/4] Plotting RD results...")
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PLOT_DIR = os.path.join(BASE, "outputs", "turing_eda")
SL_LAT_MIN, SL_LAT_MAX = 5.9, 9.9
SL_LON_MIN, SL_LON_MAX = 79.5, 81.9
extent = [SL_LON_MIN, SL_LON_MAX, SL_LAT_MIN, SL_LAT_MAX]

fig, axes = plt.subplots(1, 3, figsize=(20, 10))

im0 = axes[0].imshow(A_init, origin="lower", cmap="inferno", aspect="auto", extent=extent)
axes[0].set_title("Initial Demand (A₀)"); plt.colorbar(im0, ax=axes[0], shrink=0.6)

im1 = axes[1].imshow(A_steady, origin="lower", cmap="inferno", aspect="auto", extent=extent)
axes[1].set_title(f"Steady-State Demand (A, T={T})"); plt.colorbar(im1, ax=axes[1], shrink=0.6)

diff = A_steady - A_init
vmax = max(abs(diff.min()), abs(diff.max())) or 0.1
im2 = axes[2].imshow(diff, origin="lower", cmap="RdBu_r", aspect="auto",
                      extent=extent, vmin=-vmax, vmax=vmax)
axes[2].set_title("Change (A_steady - A_init)\nRed=demand grew, Blue=saturated")
plt.colorbar(im2, ax=axes[2], shrink=0.6)

for ax in axes:
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
fig.suptitle("Turing RD Simulation Results", fontsize=14, y=1.01)
fig.tight_layout()
fig.savefig(os.path.join(PLOT_DIR, "09_rd_simulation.png"), dpi=150, bbox_inches="tight")
plt.close()

print(f"\n  rd_demand_pressure stats:")
print(f"    mean: {outlet_feats['rd_demand_pressure'].mean():.4f}")
print(f"    std:  {outlet_feats['rd_demand_pressure'].std():.4f}")
print(f"    min:  {outlet_feats['rd_demand_pressure'].min():.4f}")
print(f"    max:  {outlet_feats['rd_demand_pressure'].max():.4f}")
print("  → Saved rd_grid.npz and updated turing_outlet_features.parquet")
print("Done! ")
