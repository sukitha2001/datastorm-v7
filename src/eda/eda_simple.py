import os, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLOT_DIR = os.path.join(BASE, "outputs", "eda_simple")
os.makedirs(PLOT_DIR, exist_ok=True)

SL_LAT_MIN, SL_LAT_MAX = 5.9, 9.9
SL_LON_MIN, SL_LON_MAX = 79.5, 81.9

print("[1/7] Loading data...")
master = pd.read_parquet(os.path.join(BASE, "data/gold/master_training_data.parquet"))
coords = pd.read_parquet(os.path.join(BASE, "data/bronze/coordinates.parquet"))
tx = pd.read_parquet(os.path.join(BASE, "data/bronze/transactions.parquet"))

df = master.merge(coords, on="Outlet_ID", how="left")
type_map = {"Grocry": "Grocery", "Bakry": "Bakery", " Eatery ": "Eatery"}
df["Outlet_Type"] = df["Outlet_Type"].str.strip().replace(type_map)
df["Outlet_Size"] = df["Outlet_Size"].str.strip().replace({"small": "Small"})

print("[2/7] GPS forensics & filtering...")
swap_mask = (df["Latitude"] > 70) | (df["Longitude"] < 10)
n_swapped = swap_mask.sum()
if n_swapped > 0:
    print(f"  fixed {n_swapped} swapped lat/lon")
    df.loc[swap_mask, ["Latitude", "Longitude"]] = df.loc[swap_mask, ["Longitude", "Latitude"]].values

oob_mask = ~(df["Latitude"].between(SL_LAT_MIN, SL_LAT_MAX) & df["Longitude"].between(SL_LON_MIN, SL_LON_MAX))
n_oob = oob_mask.sum()
df_valid = df[~oob_mask].copy()
print(f"  removed {n_oob} OOB, {len(df_valid)}/{len(df)} valid")

print("[3/7] Volume by Outlet Type & Size...")
fig, axes = plt.subplots(1, 2, figsize=(16, 6))
sns.boxplot(data=df_valid, x="Outlet_Type", y="avg_transaction_size", ax=axes[0], showfliers=False)
axes[0].set_title("Avg Transaction Size by Outlet Type")
axes[0].tick_params(axis="x", rotation=45)
sns.boxplot(data=df_valid, x="Outlet_Size", y="total_historic_volume",
            order=["Small", "Medium", "Large", "Extra Large"], ax=axes[1], showfliers=False)
axes[1].set_title("Total Volume by Outlet Size")
fig.tight_layout()
fig.savefig(os.path.join(PLOT_DIR, "volume_by_type_size.png"), dpi=150)
plt.close()
print("  → volume_by_type_size.png")

print("[4/7] Correlation heatmap...")
key_cols = [
    "Cooler_Count", "total_historic_volume", "avg_transaction_size",
    "transaction_count", "poi_restaurant_count", "poi_school_count",
    "poi_hospital_count", "poi_cafe_count", "poi_supermarket_count",
    "poi_bus_station_count"
]
corr = df_valid[key_cols].corr()
fig, ax = plt.subplots(figsize=(10, 8))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0, square=True, ax=ax)
ax.set_title("Feature Correlation Matrix")
fig.tight_layout()
fig.savefig(os.path.join(PLOT_DIR, "correlation_heatmap.png"), dpi=150)
plt.close()
print("  → correlation_heatmap.png")

print("[5/7] Monthly trends...")
tx_m = tx.groupby(["Year", "Month"]).agg(
    total_vol=("Volume_Liters", "sum"), n_outlets=("Outlet_ID", "nunique")
).reset_index()
tx_m["period"] = tx_m["Year"].astype(str) + "-" + tx_m["Month"].astype(str).str.zfill(2)
tx_m = tx_m.sort_values("period")

fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
axes[0].bar(tx_m["period"], tx_m["total_vol"], color="#5e60ce")
axes[0].set_ylabel("Total Volume (L)")
axes[0].set_title("Monthly Aggregate Volume")
axes[1].plot(tx_m["period"], tx_m["n_outlets"], "o-", color="#e63946")
axes[1].set_ylabel("Active Outlets")
axes[1].set_title("Active Outlets per Month")
plt.xticks(rotation=45, ha="right")
fig.tight_layout()
fig.savefig(os.path.join(PLOT_DIR, "monthly_trends.png"), dpi=150)
plt.close()
print("  → monthly_trends.png")

print("[6/7] Volume distribution...")
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
axes[0].hist(df_valid["total_historic_volume"], bins=80, color="#5e60ce", edgecolor="white", linewidth=0.3)
axes[0].set_xlabel("Total Historic Volume (L)")
axes[0].set_ylabel("Outlet Count")
axes[0].set_title("Volume Distribution")
axes[1].hist(np.log1p(df_valid["total_historic_volume"]), bins=80, color="#5e60ce", edgecolor="white", linewidth=0.3)
axes[1].set_xlabel("log(1 + Volume)")
axes[1].set_ylabel("Outlet Count")
axes[1].set_title("Log-Volume Distribution")
fig.tight_layout()
fig.savefig(os.path.join(PLOT_DIR, "volume_distribution.png"), dpi=150)
plt.close()
print("  → volume_distribution.png")

print("[7/7] Categorical counts, cooler/transaction EDA, top POI...")
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
type_counts = df_valid["Outlet_Type"].str.strip().value_counts()
axes[0].bar(type_counts.index, type_counts.values, color="#e63946", edgecolor="white", linewidth=0.5)
axes[0].tick_params(axis="x", rotation=45)
axes[0].set_ylabel("Outlet Count")
axes[0].set_title("Outlets by Type")
size_counts = df_valid["Outlet_Size"].str.strip().value_counts()
size_order = ["Small", "Medium", "Large", "Extra Large", "Unknown"]
size_counts = size_counts.reindex([s for s in size_order if s in size_counts.index])
axes[1].bar(size_counts.index, size_counts.values, color="#457b9d", edgecolor="white", linewidth=0.5)
axes[1].set_ylabel("Outlet Count")
axes[1].set_title("Outlets by Size")
fig.tight_layout()
fig.savefig(os.path.join(PLOT_DIR, "categorical_counts.png"), dpi=150)
plt.close()
print("  → categorical_counts.png")

fig, axes = plt.subplots(1, 3, figsize=(16, 5))
axes[0].hist(df_valid["Cooler_Count"].clip(0, 20), bins=20, color="#2a9d8f", edgecolor="white", linewidth=0.3)
axes[0].set_xlabel("Cooler Count")
axes[0].set_ylabel("Outlet Count")
axes[0].set_title("Cooler Deployment")
axes[1].hist(np.log1p(df_valid["transaction_count"]), bins=60, color="#e9c46a", edgecolor="white", linewidth=0.3)
axes[1].set_xlabel("log(1 + Transaction Count)")
axes[1].set_ylabel("Outlet Count")
axes[1].set_title("Transaction Frequency")
axes[2].hist(np.log1p(df_valid["avg_transaction_size"]), bins=60, color="#f4a261", edgecolor="white", linewidth=0.3)
axes[2].set_xlabel("log(1 + Avg Transaction Size L)")
axes[2].set_ylabel("Outlet Count")
axes[2].set_title("Avg Transaction Size")
fig.tight_layout()
fig.savefig(os.path.join(PLOT_DIR, "cooler_transaction_eda.png"), dpi=150)
plt.close()
print("  → cooler_transaction_eda.png")

poi_cols = [c for c in df_valid.columns if c.startswith("poi_")]
poi_means = df_valid[poi_cols].mean().sort_values(ascending=False).head(12)
fig, ax = plt.subplots(figsize=(10, 5))
ax.barh(poi_means.index, poi_means.values, color="#6d597a", edgecolor="white", linewidth=0.5)
ax.set_xlabel("Mean Count per Outlet")
ax.set_title("Top 12 POI Categories by Prevalence")
fig.tight_layout()
fig.savefig(os.path.join(PLOT_DIR, "top_poi_categories.png"), dpi=150)
plt.close()
print("  → top_poi_categories.png")

print(f"\nDone! All plots saved to {PLOT_DIR}")
