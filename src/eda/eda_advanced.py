import os, sys
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from scipy.ndimage import laplace

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLOT_DIR = os.path.join(BASE, "outputs", "eda_advanced")
os.makedirs(PLOT_DIR, exist_ok=True)

SL_LAT_MIN, SL_LAT_MAX = 5.9, 9.9
SL_LON_MIN, SL_LON_MAX = 79.5, 81.9

SL_BOUNDARY_FILE = "/tmp/sl_boundary.geojson"
_SL_BOUNDARY_CACHE = None

def load_sl_boundary():
    global _SL_BOUNDARY_CACHE
    if _SL_BOUNDARY_CACHE is not None:
        return _SL_BOUNDARY_CACHE
    if os.path.exists(SL_BOUNDARY_FILE):
        _SL_BOUNDARY_CACHE = gpd.read_file(SL_BOUNDARY_FILE)
    else:
        url = ("https://naturalearth.s3.amazonaws.com/10m_cultural/"
               "ne_10m_admin_0_countries.zip")
        world = gpd.read_file(url)
        _SL_BOUNDARY_CACHE = world[world["NAME"] == "Sri Lanka"]
        _SL_BOUNDARY_CACHE.to_file(SL_BOUNDARY_FILE, driver="GeoJSON")
    return _SL_BOUNDARY_CACHE

def plot_sl_boundary(ax, edgecolor="#333333", linewidth=0.8, zorder=2):
    sl = load_sl_boundary()
    sl.boundary.plot(ax=ax, edgecolor=edgecolor, linewidth=linewidth, zorder=zorder)
    ax.set_xlim(SL_LON_MIN, SL_LON_MAX)
    ax.set_ylim(SL_LAT_MIN, SL_LAT_MAX)
    ax.set_aspect("equal")

print("[1/9] Loading data...")
master = pd.read_parquet(os.path.join(BASE, "data/gold/master_training_data.parquet"))
coords = pd.read_parquet(os.path.join(BASE, "data/bronze/coordinates.parquet"))

df = master.merge(coords, on="Outlet_ID", how="left")
type_map = {"Grocry": "Grocery", "Bakry": "Bakery", " Eatery ": "Eatery"}
df["Outlet_Type"] = df["Outlet_Type"].str.strip().replace(type_map)
df["Outlet_Size"] = df["Outlet_Size"].str.strip().replace({"small": "Small"})

print("[2/9] GPS forensics...")
swap_mask = (df["Latitude"] > 70) | (df["Longitude"] < 10)
n_swapped = swap_mask.sum()
if n_swapped > 0:
    df.loc[swap_mask, ["Latitude", "Longitude"]] = df.loc[swap_mask, ["Longitude", "Latitude"]].values

oob_mask = ~(df["Latitude"].between(SL_LAT_MIN, SL_LAT_MAX) & df["Longitude"].between(SL_LON_MIN, SL_LON_MAX))
n_oob = oob_mask.sum()
print(f"  {n_swapped} swapped, {n_oob} OOB")
df_valid = df[~oob_mask].copy()
print(f"  {len(df_valid)}/{len(df)} valid outlets")

print("[3/9] Sri Lanka basemap...")
fig, ax = plt.subplots(figsize=(9, 12))
sl = load_sl_boundary()
sl.plot(ax=ax, facecolor="#e8e8e8", edgecolor="#222222", linewidth=1.2)
ax.scatter(df_valid["Longitude"], df_valid["Latitude"], s=1, alpha=0.3, c="#1a5276")
ax.set_xlim(SL_LON_MIN, SL_LON_MAX); ax.set_ylim(SL_LAT_MIN, SL_LAT_MAX)
ax.set_aspect("equal")
ax.set_title(f"Sri Lanka Outlet Network\n{len(df_valid)} outlets")
ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
fig.tight_layout()
fig.savefig(os.path.join(PLOT_DIR, "sri_lanka_basemap.png"), dpi=150)
plt.close()
print("  → sri_lanka_basemap.png")

print("[4/9] Spatial volume heatmap...")
fig, ax = plt.subplots(figsize=(8, 12))
sc = ax.scatter(
    df_valid["Longitude"], df_valid["Latitude"],
    c=np.log1p(df_valid["total_historic_volume"]),
    cmap="magma", s=2, alpha=0.5
)
plt.colorbar(sc, ax=ax, label="log(1 + Total Historic Volume)", shrink=0.6)
plot_sl_boundary(ax)
ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
ax.set_title(f"Sri Lanka Outlets  Volume Heatmap\n({len(df_valid)} valid GPS)")
fig.tight_layout()
fig.savefig(os.path.join(PLOT_DIR, "spatial_volume_heatmap.png"), dpi=150)
plt.close()
print("  → spatial_volume_heatmap.png")

print("[5/9] KMeans spatial clustering...")
kmeans = KMeans(n_clusters=8, random_state=42, n_init=10)
df_valid["spatial_cluster"] = kmeans.fit_predict(df_valid[["Latitude", "Longitude"]])

fig, axes = plt.subplots(1, 2, figsize=(16, 10))
ax = axes[0]
for c in range(8):
    m = df_valid["spatial_cluster"] == c
    ax.scatter(df_valid.loc[m, "Longitude"], df_valid.loc[m, "Latitude"],
               s=2, alpha=0.5, label=f"C{c} ({m.sum()})")
plot_sl_boundary(ax)
ax.legend(markerscale=5, fontsize=8, loc="upper left")
ax.set_title("KMeans Spatial Clusters (k=8)")

ax = axes[1]
order = df_valid.groupby("spatial_cluster")["total_historic_volume"].median().sort_values().index
sns = __import__("seaborn")
sns.boxplot(data=df_valid, x="spatial_cluster", y="total_historic_volume",
            order=order, ax=ax, showfliers=False)
ax.set_title("Volume Distribution by Cluster")
ax.set_ylabel("Total Historic Volume (L)")
fig.tight_layout()
fig.savefig(os.path.join(PLOT_DIR, "kmeans_clusters.png"), dpi=150)
plt.close()
print("  → kmeans_clusters.png")





print("[9/9] Turing RD grid computation & plots...")
CELL_SIZE = 0.01

lat_bins = np.arange(SL_LAT_MIN, SL_LAT_MAX + CELL_SIZE, CELL_SIZE)
lon_bins = np.arange(SL_LON_MIN, SL_LON_MAX + CELL_SIZE, CELL_SIZE)
n_lat = len(lat_bins) - 1
n_lon = len(lon_bins) - 1
print(f"  Grid: {n_lat}x{n_lon} = {n_lat*n_lon} cells")

df_valid["lat_bin"] = pd.cut(df_valid["Latitude"], bins=lat_bins, labels=False, include_lowest=True)
df_valid["lon_bin"] = pd.cut(df_valid["Longitude"], bins=lon_bins, labels=False, include_lowest=True)

cell_vol = df_valid.groupby(["lat_bin", "lon_bin"])["total_historic_volume"].sum()
cell_den = df_valid.groupby(["lat_bin", "lon_bin"])["Outlet_ID"].count()

A_grid = np.zeros((n_lat, n_lon))
B_grid = np.zeros((n_lat, n_lon))
for (i, j), v in cell_vol.items():
    if 0 <= i < n_lat and 0 <= j < n_lon:
        A_grid[int(i), int(j)] = v
for (i, j), v in cell_den.items():
    if 0 <= i < n_lat and 0 <= j < n_lon:
        B_grid[int(i), int(j)] = v

A_max = A_grid.max() if A_grid.max() > 0 else 1
B_max = B_grid.max() if B_grid.max() > 0 else 1
A_norm = A_grid / A_max
B_norm = B_grid / B_max

intensity = np.zeros_like(A_grid)
mask = B_grid > 0
intensity[mask] = A_grid[mask] / B_grid[mask]
intensity_norm = intensity / (intensity.max() if intensity.max() > 0 else 1)

lap_A = laplace(A_norm)
lap_B = laplace(B_norm)

extent = [SL_LON_MIN, SL_LON_MAX, SL_LAT_MIN, SL_LAT_MAX]

fig, axes = plt.subplots(1, 3, figsize=(20, 10))
im0 = axes[0].imshow(A_norm, origin="lower", cmap="inferno", aspect="auto", extent=extent)
axes[0].set_title("Activator A (Normalized Demand Volume)")
plt.colorbar(im0, ax=axes[0], shrink=0.6)
im1 = axes[1].imshow(B_norm, origin="lower", cmap="viridis", aspect="auto", extent=extent)
axes[1].set_title("Inhibitor B (Normalized Outlet Density)")
plt.colorbar(im1, ax=axes[1], shrink=0.6)
im2 = axes[2].imshow(intensity_norm, origin="lower", cmap="magma", aspect="auto", extent=extent)
axes[2].set_title("Demand Intensity (Avg Vol/Outlet/Cell)")
plt.colorbar(im2, ax=axes[2], shrink=0.6)
for ax in axes:
    plot_sl_boundary(ax, edgecolor="#555555", linewidth=0.5)
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
fig.suptitle("Turing Reaction-Diffusion Input Variables", fontsize=14, y=1.01)
fig.tight_layout()
fig.savefig(os.path.join(PLOT_DIR, "turing_rd_inputs.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  → turing_rd_inputs.png")

fig, axes = plt.subplots(1, 2, figsize=(16, 8))
vmax_a = np.percentile(np.abs(lap_A[lap_A != 0]), 99) if (lap_A != 0).any() else 0.05
vmax_b = np.percentile(np.abs(lap_B[lap_B != 0]), 99) if (lap_B != 0).any() else 0.05
im0 = axes[0].imshow(lap_A, origin="lower", cmap="RdBu_r", aspect="auto",
                      extent=extent, vmin=-vmax_a, vmax=vmax_a)
axes[0].set_title("∇²A (Demand Laplacian)")
plt.colorbar(im0, ax=axes[0], shrink=0.6)
im1 = axes[1].imshow(lap_B, origin="lower", cmap="RdBu_r", aspect="auto",
                      extent=extent, vmin=-vmax_b, vmax=vmax_b)
axes[1].set_title("∇²B (Density Laplacian)")
plt.colorbar(im1, ax=axes[1], shrink=0.6)
for ax in axes:
    plot_sl_boundary(ax, edgecolor="#555555", linewidth=0.5)
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
fig.suptitle("Laplacian Fields  Diffusion Tendency", fontsize=14, y=1.01)
fig.tight_layout()
fig.savefig(os.path.join(PLOT_DIR, "laplacian_fields.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  → laplacian_fields.png")

cell_stats = df_valid.groupby(["lat_bin", "lon_bin"]).agg(
    n_outlets=("Outlet_ID", "count"),
    total_vol=("total_historic_volume", "sum"),
    avg_vol=("total_historic_volume", "mean"),
    avg_coolers=("Cooler_Count", "mean"),
    avg_tx_size=("avg_transaction_size", "mean"),
).reset_index()

fig, axes = plt.subplots(2, 2, figsize=(14, 12))
axes[0, 0].scatter(cell_stats["n_outlets"], cell_stats["total_vol"], s=8, alpha=0.4, c="#e63946")
axes[0, 0].set_xlabel("Outlets per Cell"); axes[0, 0].set_ylabel("Total Volume per Cell")
axes[0, 0].set_title("Outlet Density vs Demand (per cell)")
axes[0, 1].scatter(cell_stats["n_outlets"], cell_stats["avg_vol"], s=8, alpha=0.4, c="#457b9d")
axes[0, 1].set_xlabel("Outlets per Cell"); axes[0, 1].set_ylabel("Avg Volume per Outlet")
axes[0, 1].set_title("Density vs Per-Outlet Demand")
axes[1, 0].scatter(cell_stats["avg_coolers"], cell_stats["avg_vol"], s=8, alpha=0.4, c="#2a9d8f")
axes[1, 0].set_xlabel("Avg Coolers per Outlet"); axes[1, 0].set_ylabel("Avg Volume per Outlet")
axes[1, 0].set_title("Cooler Capacity vs Demand")
axes[1, 1].scatter(cell_stats["n_outlets"], cell_stats["avg_tx_size"], s=8, alpha=0.4, c="#e9c46a")
axes[1, 1].set_xlabel("Outlets per Cell"); axes[1, 1].set_ylabel("Avg Transaction Size")
axes[1, 1].set_title("Density vs Transaction Size")
fig.suptitle("Cell-Level Turing Variable Relationships", fontsize=14)
fig.tight_layout()
fig.savefig(os.path.join(PLOT_DIR, "cell_scatter.png"), dpi=150)
plt.close()
print("  → cell_scatter.png")

np.savez(
    os.path.join(BASE, "data/gold/turing_rd_inputs.npz"),
    A_norm=A_norm, B_norm=B_norm, intensity_norm=intensity_norm,
    lap_A=lap_A, lap_B=lap_B,
    lat_bins=lat_bins, lon_bins=lon_bins,
    cell_size=CELL_SIZE, grid_shape=np.array([n_lat, n_lon])
)

df_valid["cell_demand_A"] = df_valid.apply(
    lambda r: A_norm[int(r["lat_bin"]), int(r["lon_bin"])]
    if pd.notna(r["lat_bin"]) and pd.notna(r["lon_bin"]) else 0, axis=1)
df_valid["cell_density_B"] = df_valid.apply(
    lambda r: B_norm[int(r["lat_bin"]), int(r["lon_bin"])]
    if pd.notna(r["lat_bin"]) and pd.notna(r["lon_bin"]) else 0, axis=1)
df_valid["cell_intensity"] = df_valid.apply(
    lambda r: intensity_norm[int(r["lat_bin"]), int(r["lon_bin"])]
    if pd.notna(r["lat_bin"]) and pd.notna(r["lon_bin"]) else 0, axis=1)
df_valid["laplacian_A"] = df_valid.apply(
    lambda r: lap_A[int(r["lat_bin"]), int(r["lon_bin"])]
    if pd.notna(r["lat_bin"]) and pd.notna(r["lon_bin"]) else 0, axis=1)

out_cols = ["Outlet_ID", "Latitude", "Longitude", "spatial_cluster",
            "lat_bin", "lon_bin", "cell_demand_A", "cell_density_B",
            "cell_intensity", "laplacian_A"]
df_valid[out_cols].to_parquet(
    os.path.join(BASE, "data/gold/turing_outlet_features.parquet"), index=False)

print(f"\nGrid: {n_lat}x{n_lon} = {n_lat*n_lon} cells")
print(f"Cell size: {CELL_SIZE}°")
print(f"Non-empty cells: {int((A_grid > 0).sum())}/{n_lat*n_lon}")
print(f"Max volume/cell: {A_grid.max():,.0f} L")
print(f"Max outlets/cell: {int(B_grid.max())}")
print(f"All plots saved to {PLOT_DIR}")
print("Done!")
