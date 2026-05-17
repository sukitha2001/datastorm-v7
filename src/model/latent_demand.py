#!/usr/bin/env python3
"""
Latent Demand Estimation  Agent D Modeling Pipeline
=====================================================
Implements:
1. Feature engineering (Gold layer merge)
2. Censoring threshold estimation
3. Tobit-style censored regression
4. Peer-group uplift (90th percentile ceiling)
5. Stochastic Frontier Analysis (log-normal)
6. Ensemble prediction for Jan 2026
"""
import os
import warnings
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.neighbors import NearestNeighbors
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLOT_DIR = os.path.join(BASE, "outputs", "model")
os.makedirs(PLOT_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════
# STEP 1: Build model-ready feature matrix
# ══════════════════════════════════════════════════════════════════════
print("=" * 60)
print("STEP 1: Building feature matrix")
print("=" * 60)

master = pd.read_parquet(os.path.join(BASE, "data/gold/master_training_data.parquet"))
coords = pd.read_parquet(os.path.join(BASE, "data/bronze/coordinates.parquet"))
tx = pd.read_parquet(os.path.join(BASE, "data/bronze/transactions.parquet"))
seas = pd.read_parquet(os.path.join(BASE, "data/bronze/seasonality.parquet"))

# Load Turing features if available
turing_path = os.path.join(BASE, "data/gold/turing_outlet_features.parquet")
has_turing = os.path.exists(turing_path)
if has_turing:
    turing_feats = pd.read_parquet(turing_path)
    print(f"  ✓ Turing features loaded ({len(turing_feats)} outlets)")

# Merge coordinates
df = master.merge(coords, on="Outlet_ID", how="left")

# Fix GPS
swap_mask = (df["Latitude"] > 70) | (df["Longitude"] < 10)
df.loc[swap_mask, ["Latitude", "Longitude"]] = df.loc[swap_mask, ["Longitude", "Latitude"]].values
oob = ~(df["Latitude"].between(5.9, 9.9) & df["Longitude"].between(79.5, 81.9))
df.loc[oob, ["Latitude", "Longitude"]] = [7.5, 80.0]  # impute with centroid

# Clean outlet type/size
type_map = {"Grocry": "Grocery", "Bakry": "Bakery", " Eatery ": "Eatery"}
df["Outlet_Type"] = df["Outlet_Type"].str.strip().replace(type_map)
df["Outlet_Size"] = df["Outlet_Size"].str.strip().replace({"small": "Small"})

# ── Monthly-level features from transactions ────────────────────────
print("  Computing monthly-level features...")
tx_outlet = tx.groupby(["Outlet_ID", "Year", "Month"]).agg(
    monthly_vol=("Volume_Liters", "sum"),
    monthly_bill=("Total_Bill_Value", "sum"),
    monthly_tx=("Volume_Liters", "count")
).reset_index()

# Per-outlet time series features
outlet_ts = tx_outlet.groupby("Outlet_ID").agg(
    avg_monthly_volume=("monthly_vol", "mean"),
    max_monthly_volume=("monthly_vol", "max"),
    min_monthly_volume=("monthly_vol", "min"),
    std_monthly_volume=("monthly_vol", "std"),
    n_active_months=("monthly_vol", "count"),
    avg_monthly_bill=("monthly_bill", "mean"),
    avg_monthly_tx=("monthly_tx", "mean"),
).reset_index()

# Coefficient of variation (low CV + high volume = likely capped)
outlet_ts["volume_cv"] = outlet_ts["std_monthly_volume"] / (outlet_ts["avg_monthly_volume"] + 1e-8)

# ── Flatline detection (near-identical volume for 4+ consecutive months) ──
print("  Detecting flatline & round-number censoring signals...")
tx_outlet_sorted = tx_outlet.sort_values(["Outlet_ID", "Year", "Month"])

def detect_flatline(group, n_months=4, tolerance=0.05):
    """Check if outlet has near-identical volume for n+ consecutive months."""
    vols = group["monthly_vol"].values
    if len(vols) < n_months:
        return 0
    max_run = 1
    current_run = 1
    for i in range(1, len(vols)):
        if abs(vols[i] - vols[i-1]) / (vols[i-1] + 1e-8) < tolerance:
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 1
    return 1 if max_run >= n_months else 0

def detect_round_numbers(group, threshold=0.6):
    """Flag outlets where >60% of monthly volumes are round numbers."""
    vols = group["monthly_vol"].values
    if len(vols) < 3:
        return 0
    round_count = sum(1 for v in vols if v > 0 and v % 10 == 0)
    return 1 if round_count / len(vols) > threshold else 0

flatline_flags = tx_outlet_sorted.groupby("Outlet_ID").apply(detect_flatline).reset_index()
flatline_flags.columns = ["Outlet_ID", "flatline_flag"]

round_flags = tx_outlet_sorted.groupby("Outlet_ID").apply(detect_round_numbers).reset_index()
round_flags.columns = ["Outlet_ID", "round_number_flag"]

# Merge both signals
flatline_flags = flatline_flags.merge(round_flags, on="Outlet_ID", how="left")
flatline_flags["censoring_signal"] = ((flatline_flags["flatline_flag"] == 1) |
                                       (flatline_flags["round_number_flag"] == 1)).astype(int)
n_flatline = flatline_flags["flatline_flag"].sum()
n_round = flatline_flags["round_number_flag"].sum()
n_any = flatline_flags["censoring_signal"].sum()
print(f"  ⚠ {n_flatline} outlets flagged as flatline (4+ months within 5%)")
print(f"  ⚠ {n_round} outlets flagged as round-number pattern")
print(f"  ⚠ {n_any} outlets with ANY censoring signal")

# ── January seasonality index ────────────────────────────────────────
print("  Computing January seasonality index...")
jan_vol = tx_outlet[tx_outlet["Month"] == 1].groupby("Outlet_ID")["monthly_vol"].mean()
annual_avg = tx_outlet.groupby("Outlet_ID")["monthly_vol"].mean()
jan_idx = (jan_vol / annual_avg).fillna(1.0).clip(0.5, 2.0)
jan_idx = jan_idx.reset_index()
jan_idx.columns = ["Outlet_ID", "jan_seasonality_idx"]

# ── Distributor mapping ──────────────────────────────────────────────
# Get primary distributor per outlet
dist_map = tx.groupby("Outlet_ID")["Distributor_ID"].agg(lambda x: x.mode().iloc[0] if len(x) > 0 else "Unknown")
dist_map = dist_map.reset_index()
dist_map.columns = ["Outlet_ID", "primary_distributor"]

# Distributor Jan seasonality
jan_seas = seas[(seas["Month"] == 1)].copy()
jan_seas["seas_score"] = jan_seas["Seasonality_Index"].map(
    {"Favorable": 1.2, "Moderate": 1.0, "Un-Favorable": 0.8}
).fillna(1.0)
dist_jan_seas = jan_seas.groupby("Distributor_ID")["seas_score"].mean().reset_index()
dist_jan_seas.columns = ["primary_distributor", "dist_jan_seasonality"]

# ── Merge everything ─────────────────────────────────────────────────
print("  Merging all features...")
df = df.merge(outlet_ts, on="Outlet_ID", how="left")
df = df.merge(flatline_flags, on="Outlet_ID", how="left")
df = df.merge(jan_idx, on="Outlet_ID", how="left")
df = df.merge(dist_map, on="Outlet_ID", how="left")
df = df.merge(dist_jan_seas, on="primary_distributor", how="left")

if has_turing:
    # Exclude spatial cols that already exist in df from coords merge
    exclude = {"Outlet_ID", "Latitude", "Longitude", "lat_bin", "lon_bin"}
    turing_cols = [c for c in turing_feats.columns if c not in exclude]
    df = df.merge(turing_feats[["Outlet_ID"] + turing_cols], on="Outlet_ID", how="left")

# Fill NAs
df["flatline_flag"] = df["flatline_flag"].fillna(0).astype(int)
df["jan_seasonality_idx"] = df["jan_seasonality_idx"].fillna(1.0)
df["dist_jan_seasonality"] = df["dist_jan_seasonality"].fillna(1.0)

for c in df.select_dtypes(include="number").columns:
    df[c] = df[c].fillna(0)

# ── Encode categoricals ─────────────────────────────────────────────
le_type = LabelEncoder()
df["outlet_type_enc"] = le_type.fit_transform(df["Outlet_Type"])

size_order = {"Small": 0, "Medium": 1, "Large": 2, "Extra Large": 3}
df["outlet_size_enc"] = df["Outlet_Size"].map(size_order).fillna(0).astype(int)

le_dist = LabelEncoder()
df["distributor_enc"] = le_dist.fit_transform(df["primary_distributor"].fillna("Unknown"))

print(f"  ✓ Feature matrix: {df.shape[0]} rows × {df.shape[1]} cols")

# ══════════════════════════════════════════════════════════════════════
# STEP 2: Censoring Framework
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 2: Censoring threshold estimation")
print("=" * 60)

# Constraint score: composite of volume CV, censoring signals, and size
# Low CV + high volume + censoring signal = likely constrained
df["constraint_score"] = (
    (1.0 - df["volume_cv"].clip(0, 2) / 2) * 0.3 +  # Low CV → high score
    df["flatline_flag"] * 0.25 +                      # Flatline → high score
    df["round_number_flag"] * 0.15 +                   # Round numbers → constraint artifact
    df["censoring_signal"] * 0.15 +                    # Any censoring signal
    (df["outlet_size_enc"] / 3) * 0.15                 # Larger outlets more likely constrained
)
df["constraint_score"] = df["constraint_score"].clip(0, 1)

# Determine censoring threshold per outlet
def compute_threshold(row):
    cs = row["constraint_score"]
    max_vol = row["max_monthly_volume"]
    if cs > 0.7 and row["censoring_signal"] == 1:
        return max_vol * 1.05  # Almost certainly capped
    elif cs > 0.5:
        return max_vol * 1.15  # Probably constrained
    elif cs > 0.3:
        return max_vol * 1.30  # Possibly constrained
    else:
        return np.inf  # Likely unconstrained

df["censoring_threshold"] = df.apply(compute_threshold, axis=1)
n_censored = (df["censoring_threshold"] < np.inf).sum()
n_hard = ((df["constraint_score"] > 0.7) & (df["censoring_signal"] == 1)).sum()
n_soft = ((df["constraint_score"] > 0.3) & (df["constraint_score"] <= 0.7)).sum()
print(f"  Hard-censored (score>0.7 + signal):   {n_hard}")
print(f"  Soft-censored (score 0.3-0.7):        {n_soft}")
print(f"  Total censored:                       {n_censored}")
print(f"  Unconstrained:                        {len(df) - n_censored}")

# ══════════════════════════════════════════════════════════════════════
# STEP 3: Tobit-style Censored Regression
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 3: Tobit-style censored regression")
print("=" * 60)

# Feature columns  ONLY causal/structural features, NOT derived volume metrics
# (avg_monthly_volume, avg_monthly_bill, transaction_count are near-identical to target)
feature_cols = [
    "Cooler_Count", "n_active_months", "volume_cv",
    "outlet_type_enc", "outlet_size_enc", "distributor_enc",
    "Latitude", "Longitude",
    "poi_restaurant_count", "poi_school_count", "poi_hospital_count",
    "poi_cafe_count", "poi_supermarket_count", "poi_bus_station_count",
]

if has_turing and "rd_demand_pressure" in df.columns:
    feature_cols += ["rd_demand_pressure", "cell_demand_A", "cell_density_B", "cell_intensity"]
    print("  ✓ Including Turing RD features")

print(f"  Using {len(feature_cols)} non-leaky features (no volume-derived cols)")
X = df[feature_cols].values
y_observed = df["max_monthly_volume"].values  # Use MAX (ceiling signal)

# Identify censored vs uncensored observations
is_censored = df["censoring_threshold"] < np.inf

# --- Tobit approach: fit on unconstrained outlets, predict for all ---
unconstrained_mask = ~is_censored
print(f"  Training on {unconstrained_mask.sum()} unconstrained outlets")

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

X_train = X_scaled[unconstrained_mask]
y_train = y_observed[unconstrained_mask]

# GradientBoosting for non-linear relationships (Cooler→Volume is non-linear)
model = GradientBoostingRegressor(
    n_estimators=300, max_depth=5, learning_rate=0.1,
    subsample=0.8, random_state=42, min_samples_leaf=20
)
model.fit(X_train, y_train)

# Predict for ALL outlets (including constrained)
y_tobit = model.predict(X_scaled)
y_tobit = np.maximum(y_tobit, 0)  # No negatives

r2_train = model.score(X_train, y_train)
print(f"  Training R² (unconstrained): {r2_train:.4f}")

# Feature importance
feat_imp = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False)
print(f"  Top features:")
for feat, imp in feat_imp.head(6).items():
    print(f"    {feat}: {imp:.3f}")
print(f"  Tobit predictions  mean: {y_tobit.mean():.1f}, "
      f"max: {y_tobit.max():.1f}, min: {y_tobit.min():.1f}")

# ══════════════════════════════════════════════════════════════════════
# STEP 4: Peer Group Uplift (90th percentile ceiling)
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 4: Peer group uplift")
print("=" * 60)

# Find 20 nearest peers based on outlet_type, outlet_size, and POI score
peer_features = df[["outlet_type_enc", "outlet_size_enc", "Cooler_Count",
                     "poi_restaurant_count", "poi_school_count"]].values
peer_scaler = StandardScaler()
peer_scaled = peer_scaler.fit_transform(peer_features)

nn = NearestNeighbors(n_neighbors=21, metric="euclidean")  # 21 because includes self
nn.fit(peer_scaled)
distances, indices = nn.kneighbors(peer_scaled)

# For each outlet, get 90th percentile of peer volumes
peer_90th = np.zeros(len(df))
for i in range(len(df)):
    peer_idx = indices[i, 1:]  # Exclude self
    peer_vols = y_observed[peer_idx]
    peer_90th[i] = np.percentile(peer_vols, 90)

# Sanity cap: predictions should not exceed 3× peer 90th percentile
peer_cap = peer_90th * 3.0
print(f"  Peer 90th percentile  mean: {peer_90th.mean():.1f}, max: {peer_90th.max():.1f}")

# ══════════════════════════════════════════════════════════════════════
# STEP 5: Stochastic Frontier Analysis (simplified)
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 5: Stochastic Frontier Analysis")
print("=" * 60)

# SFA concept: the "frontier" is the maximum demand any outlet with
# similar characteristics could achieve. The gap between observed and
# frontier = inefficiency = latent potential.

# Group by outlet_size × outlet_type for finer frontier estimation
sfa_frontier = np.zeros(len(df))
for size in df["Outlet_Size"].unique():
    for otype in df["Outlet_Type"].unique():
        group_mask = (df["Outlet_Size"] == size) & (df["Outlet_Type"] == otype)
        if group_mask.sum() < 10:
            # Fall back to size-only group if too few
            group_mask = df["Outlet_Size"] == size
        
        group_vols = y_observed[group_mask]
        
        # Frontier = 95th percentile of similar outlets
        frontier_val = np.percentile(group_vols, 95)
        
        # Only apply to the specific size×type intersection
        specific_mask = (df["Outlet_Size"] == size) & (df["Outlet_Type"] == otype)
        specific_vols = y_observed[specific_mask]
        constraint_factor = df.loc[specific_mask, "constraint_score"].values
        cooler_factor = df.loc[specific_mask, "Cooler_Count"].values / (df.loc[specific_mask, "Cooler_Count"].max() + 1e-8)
        
        # Higher constraint + more cooler capacity → more uplift potential
        uplift_weight = constraint_factor * 0.6 + cooler_factor * 0.4
        sfa_pred = specific_vols + (frontier_val - specific_vols) * uplift_weight * 0.5
        sfa_frontier[specific_mask] = np.maximum(sfa_pred, specific_vols)

print(f"  SFA frontier  mean: {sfa_frontier.mean():.1f}, max: {sfa_frontier.max():.1f}")

# ══════════════════════════════════════════════════════════════════════
# STEP 6: Ensemble & January Adjustment
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 6: Ensemble prediction for January 2026")
print("=" * 60)

# Ensemble weights
W_TOBIT = 0.50
W_SFA = 0.30
W_PEER = 0.20

raw_ensemble = (
    y_tobit * W_TOBIT +
    sfa_frontier * W_SFA +
    peer_90th * W_PEER
)

# Apply January seasonality adjustment
jan_adj = df["jan_seasonality_idx"].values * df["dist_jan_seasonality"].values
raw_jan = raw_ensemble * jan_adj

# Floor: never predict below observed maximum
max_observed = df["max_monthly_volume"].values
final_pred = np.maximum(raw_jan, max_observed)

# Cap: don't exceed 3× peer 90th percentile
final_pred = np.minimum(final_pred, peer_cap)

# Final floor: ensure we never go below observed max after capping
final_pred = np.maximum(final_pred, max_observed)

# For very small outlets with max_vol=0, use the model prediction
zero_mask = max_observed == 0
final_pred[zero_mask] = np.maximum(raw_jan[zero_mask], 1.0)

# Round to 2 decimal places
final_pred = np.round(final_pred, 2)

df["Maximum_Monthly_Liters"] = final_pred

print(f"  Final predictions:")
print(f"    Mean:   {final_pred.mean():.2f} L")
print(f"    Median: {np.median(final_pred):.2f} L")
print(f"    Min:    {final_pred.min():.2f} L")
print(f"    Max:    {final_pred.max():.2f} L")
print(f"    Std:    {final_pred.std():.2f} L")

# ══════════════════════════════════════════════════════════════════════
# STEP 7: Validation & Output
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 7: Validation & output")
print("=" * 60)

output_df = df[["Outlet_ID", "Maximum_Monthly_Liters"]].copy()

# Validation checks
n_rows = len(output_df)
n_nulls = output_df["Maximum_Monthly_Liters"].isna().sum()
n_negative = (output_df["Maximum_Monthly_Liters"] < 0).sum()
n_unique_ids = output_df["Outlet_ID"].nunique()

print(f"  Rows:         {n_rows} {'' if n_rows == 20000 else '❌'}")
print(f"  Null values:  {n_nulls} {'' if n_nulls == 0 else '❌'}")
print(f"  Negatives:    {n_negative} {'' if n_negative == 0 else '❌'}")
print(f"  Unique IDs:   {n_unique_ids} {'' if n_unique_ids == 20000 else '❌'}")

# Save predictions
out_dir = os.path.join(BASE, "data/predictions")
os.makedirs(out_dir, exist_ok=True)
output_df.to_csv(os.path.join(out_dir, "ctrl_freaks_predictions.csv"), index=False)
print(f"\n  → Saved ctrl_freaks_predictions.csv ({n_rows} rows)")

# ══════════════════════════════════════════════════════════════════════
# STEP 8: Diagnostic Plots
# ══════════════════════════════════════════════════════════════════════
print("\n  Generating diagnostic plots...")

# Plot 1: Observed vs Predicted
fig, axes = plt.subplots(2, 2, figsize=(16, 14))

ax = axes[0, 0]
ax.scatter(df["avg_monthly_volume"], df["Maximum_Monthly_Liters"], s=2, alpha=0.3, c="#e63946")
max_val = max(df["avg_monthly_volume"].max(), df["Maximum_Monthly_Liters"].max())
ax.plot([0, max_val], [0, max_val], "k--", alpha=0.5, label="y=x (no uplift)")
ax.set_xlabel("Observed Avg Monthly Volume (L)")
ax.set_ylabel("Predicted Maximum Monthly Liters")
ax.set_title("Observed vs Predicted (Latent Potential)")
ax.legend()

# Plot 2: Uplift ratio distribution
ax = axes[0, 1]
uplift = df["Maximum_Monthly_Liters"] / (df["avg_monthly_volume"] + 1e-8)
ax.hist(uplift.clip(0, 5), bins=100, color="#457b9d", edgecolor="none", alpha=0.8)
ax.axvline(1.0, color="red", linestyle="--", label="No uplift (1.0)")
ax.set_xlabel("Uplift Ratio (Predicted / Observed)")
ax.set_ylabel("Count")
ax.set_title(f"Uplift Distribution (median: {uplift.median():.2f}x)")
ax.legend()

# Plot 3: Predictions by Outlet Size
ax = axes[1, 0]
order = ["Small", "Medium", "Large", "Extra Large"]
sns.boxplot(data=df, x="Outlet_Size", y="Maximum_Monthly_Liters",
            order=order, ax=ax, showfliers=False)
ax.set_title("Predicted Max Volume by Outlet Size")
ax.set_ylabel("Maximum Monthly Liters")

# Plot 4: Constraint score vs uplift
ax = axes[1, 1]
ax.scatter(df["constraint_score"], uplift.clip(0, 5), s=2, alpha=0.3, c="#2a9d8f")
ax.set_xlabel("Constraint Score")
ax.set_ylabel("Uplift Ratio")
ax.set_title("Constrained Outlets Get More Uplift")
ax.axhline(1.0, color="red", linestyle="--", alpha=0.5)

fig.suptitle("Latent Demand Estimation  Diagnostics", fontsize=14)
fig.tight_layout()
fig.savefig(os.path.join(PLOT_DIR, "01_model_diagnostics.png"), dpi=150)
plt.close()
print("  → Saved 01_model_diagnostics.png")

# Plot 5: Spatial prediction map
fig, axes = plt.subplots(1, 2, figsize=(16, 10))
sc0 = axes[0].scatter(df["Longitude"], df["Latitude"],
                       c=np.log1p(df["avg_monthly_volume"]), cmap="magma", s=2, alpha=0.5)
axes[0].set_title("Observed Avg Monthly Volume (log)")
plt.colorbar(sc0, ax=axes[0], shrink=0.6)

sc1 = axes[1].scatter(df["Longitude"], df["Latitude"],
                       c=np.log1p(df["Maximum_Monthly_Liters"]), cmap="magma", s=2, alpha=0.5)
axes[1].set_title("Predicted Maximum Monthly Liters (log)")
plt.colorbar(sc1, ax=axes[1], shrink=0.6)

for ax in axes:
    ax.set_xlim(79.5, 81.9); ax.set_ylim(5.9, 9.9)
    ax.set_aspect("equal")
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
fig.suptitle("Spatial: Observed vs Predicted Demand", fontsize=14)
fig.tight_layout()
fig.savefig(os.path.join(PLOT_DIR, "02_spatial_predictions.png"), dpi=150)
plt.close()
print("  → Saved 02_spatial_predictions.png")

# ── Summary table by outlet size ─────────────────────────────────────
print("\n" + "=" * 60)
print("PREDICTION SUMMARY BY OUTLET SIZE")
print("=" * 60)
summary = df.groupby("Outlet_Size").agg(
    count=("Maximum_Monthly_Liters", "count"),
    observed_mean=("avg_monthly_volume", "mean"),
    predicted_mean=("Maximum_Monthly_Liters", "mean"),
    predicted_median=("Maximum_Monthly_Liters", "median"),
).round(1)
summary["uplift_pct"] = ((summary["predicted_mean"] / summary["observed_mean"] - 1) * 100).round(1)
print(summary.to_string())

print("\nPipeline complete!")
