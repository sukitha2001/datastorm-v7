#!/usr/bin/env python3
"""
Marketing Spend Optimization
Allocate LKR 5M promotional budget across Western Province outlets
to maximize incremental volume for January 2026.

Assigns each outlet a spend type:
  - discount       : price-sensitive, high-volume, credit-constrained outlets
  - merchandising  : high-footfall outlets (coolers, POS displays, billboards)
  - promotional    : sampling, events at footfall-dense or diverse-catchment outlets
"""

import os
import sys

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(BASE, "data", "budget")
os.makedirs(OUT_DIR, exist_ok=True)

WESTERN_DISTRIBUTORS = ["DIST_W_01", "DIST_W_02", "DIST_W_03"]
BUDGET = 5_000_000

print("=" * 60)
print("Marketing Spend Optimization")
print("=" * 60)

# ── Load inputs ────────────────────────────────────────────────────
pred_path = os.path.join(BASE, "data", "predictions", "ctrl_freaks_predictions.csv")
if not os.path.exists(pred_path):
    print(f"[ERROR] Predictions not found at {pred_path}")
    sys.exit(1)

pred = pd.read_csv(pred_path)
print(f"[1/5] Loaded predictions: {len(pred)} outlets")

tx = pd.read_parquet(os.path.join(BASE, "data", "silver", "sales.parquet"))
outlets = pd.read_parquet(os.path.join(BASE, "data", "silver", "outlets.parquet"))

# ── Spend-type determination ───────────────────────────────────────
# Base mapping from outlet type to spend type
TYPE_MAP = {
    "Eatery": "promotional",
    "Hotel": "promotional",
    "Bakery": "promotional",
    "Bakry": "promotional",
    "Pharmacy": "merchandising",
    "Kiosk": "merchandising",
    "SMMT": "merchandising",
    "Grocery": "discount",
    "Grocry": "discount",
}

# Per-outlet stats for type assignment
vol_stats = (
    tx[tx["Distributor_ID"].isin(WESTERN_DISTRIBUTORS)]
    .groupby("Outlet_ID")["Volume_Liters"]
    .agg(["mean", "std", "max"])
    .reset_index()
)
vol_stats["volume_cv"] = np.where(
    vol_stats["mean"] > 0, vol_stats["std"] / vol_stats["mean"], 0
)

# Per-outlet flatline flag (max across months — 1 if ever flatlined)
flatline = (
    tx[tx["Distributor_ID"].isin(WESTERN_DISTRIBUTORS)]
    .groupby("Outlet_ID")["flatline_flag"]
    .max()
    .reset_index()
)

western_info = (
    outlets.merge(vol_stats, on="Outlet_ID", how="left")
    .merge(flatline, on="Outlet_ID", how="left")
    .fillna({"volume_cv": 0, "flatline_flag": 0})
)

western_info["spend_type"] = (
    western_info["Outlet_Type"].str.strip().map(TYPE_MAP).fillna("discount")
)

# Overrides
western_info.loc[western_info["flatline_flag"] == 1, "spend_type"] = "discount"
western_info.loc[western_info["constraint_flag"] == 1, "spend_type"] = "discount"
western_info.loc[
    (western_info["Cooler_Count"] == 0) & (western_info["spend_type"] != "discount"),
    "spend_type",
] = "merchandising"

# ── Filter Western outlets with upside ──────────────────────────
western_tx = tx[tx["Distributor_ID"].isin(WESTERN_DISTRIBUTORS)].copy()
hist_max = western_tx.groupby("Outlet_ID")["Volume_Liters"].max().reset_index()
hist_max.columns = ["Outlet_ID", "historical_max_volume"]

western_pred = pred[pred["Outlet_ID"].isin(hist_max["Outlet_ID"])].copy()
western_pred = western_pred.merge(hist_max, on="Outlet_ID", how="left")

upside = (
    western_pred["Maximum_Monthly_Liters"].to_numpy()
    - western_pred["historical_max_volume"].to_numpy()
)
western_pred["incremental_volume"] = np.clip(upside, 0, None)
western_pred = western_pred[western_pred["incremental_volume"] > 0].copy()

# Per-outlet distributor (use most common)
distributor = (
    western_tx.groupby("Outlet_ID")["Distributor_ID"]
    .agg(lambda x: x.mode().iloc[0] if len(x.mode()) else x.iloc[0])
    .reset_index()
)

# Attach spend type + metadata
western_pred = western_pred.merge(
    western_info[
        ["Outlet_ID", "spend_type", "volume_cv", "Cooler_Count", "Outlet_Type", "Outlet_Size", "constraint_flag"]
    ],
    on="Outlet_ID",
    how="left",
).merge(
    distributor, on="Outlet_ID", how="left"
).fillna(
    {
        "spend_type": "discount",
        "volume_cv": 0,
        "Cooler_Count": 0,
        "Outlet_Type": "Unknown",
        "Outlet_Size": "Unknown",
        "constraint_flag": 0,
        "Distributor_ID": "Unknown",
    }
)

western_pred = western_pred.sort_values(
    "incremental_volume", ascending=False
).reset_index(drop=True)

print(f"[2/5] Western outlets with upside: {len(western_pred)}")
print(f"      Total upside: {western_pred['incremental_volume'].sum():.0f} L")
type_counts = western_pred["spend_type"].value_counts()
for t, c in type_counts.items():
    print(f"      {t}: {c} outlets")

# ── Tiered allocation ─────────────────────────────────────────────
n = len(western_pred)
western_pred["tier"] = np.where(
    western_pred.index < int(n * 0.05),
    "tier_1_high",
    np.where(western_pred.index < int(n * 0.20), "tier_2_medium", "tier_3_low"),
)

BUDGET_SPLIT = {"tier_1_high": 0.45, "tier_2_medium": 0.35, "tier_3_low": 0.20}
CAPS = {"tier_1_high": 150_000, "tier_2_medium": 60_000, "tier_3_low": 10_000}

allocation = []
remaining = float(BUDGET)

for tier_name in ["tier_1_high", "tier_2_medium", "tier_3_low"]:
    tier_df = western_pred[western_pred["tier"] == tier_name].copy()
    if len(tier_df) == 0:
        continue

    tier_budget = min(BUDGET * BUDGET_SPLIT[tier_name], remaining)
    total_upside = tier_df["incremental_volume"].sum()
    cap = CAPS[tier_name]

    for _, row in tier_df.iterrows():
        if remaining <= 0:
            break
        share = (
            row["incremental_volume"] / total_upside
            if total_upside > 0
            else 1.0 / len(tier_df)
        )
        spend = min(share * tier_budget, cap, remaining)
        if spend < 1000:
            continue
        allocation.append(
            {
                "Outlet_ID": row["Outlet_ID"],
                "Distributor_ID": row["Distributor_ID"],
                "Outlet_Type": row["Outlet_Type"],
                "Outlet_Size": row["Outlet_Size"],
                "Cooler_Count": int(row["Cooler_Count"]),
                "constraint_flag": int(row["constraint_flag"]),
                "volume_cv": round(row["volume_cv"], 3),
                "historical_max_volume": int(row["historical_max_volume"]),
                "Maximum_Monthly_Liters": int(row["Maximum_Monthly_Liters"]),
                "incremental_volume": int(row["incremental_volume"]),
                "Trade_Spend_LKR": round(spend, 2),
                "Spend_Type": row["spend_type"],
            }
        )
        remaining -= spend

alloc_df = pd.DataFrame(allocation)

# ── Remaining budget sweep ──────────────────────────────────────
if remaining > 5000 and len(allocation) > 0:
    total_spent = sum(a["Trade_Spend_LKR"] for a in allocation)
    for a in allocation:
        a["Trade_Spend_LKR"] = round(
            a["Trade_Spend_LKR"] + remaining * (a["Trade_Spend_LKR"] / total_spent), 2
        )
    remaining = 0
    alloc_df = pd.DataFrame(allocation)

total_spend = alloc_df["Trade_Spend_LKR"].sum() if len(alloc_df) > 0 else 0

print("[3/5] Allocation complete")
print(f"      Outlets funded: {len(alloc_df)}")
print(f"      Total spend: LKR {total_spend:,.0f}")
print(f"      Remaining: LKR {remaining:,.0f}")
print("      Spend type breakdown:")
for t, g in alloc_df.groupby("Spend_Type"):
    print(f"        {t}: {len(g)} outlets, LKR {g['Trade_Spend_LKR'].sum():,.0f} total")

tier_counts = western_pred[western_pred["Outlet_ID"].isin(alloc_df["Outlet_ID"])][
    "tier"
].value_counts()
for t in ["tier_1_high", "tier_2_medium", "tier_3_low"]:
    c = tier_counts.get(t, 0)
    s = (
        alloc_df[
            alloc_df["Outlet_ID"].isin(
                western_pred[western_pred["tier"] == t]["Outlet_ID"]
            )
        ]["Trade_Spend_LKR"].sum()
        if c > 0
        else 0
    )
    avg = s / c if c > 0 else 0
    print(f"        {t}: {c} outlets, avg LKR {avg:,.0f}")

# ── Output ────────────────────────────────────────────────────────
out_path = os.path.join(OUT_DIR, "ctrl_freaks_budget_mapping.csv")
cols = [
    "Outlet_ID", "Distributor_ID", "Outlet_Type", "Outlet_Size",
    "Cooler_Count", "constraint_flag", "volume_cv",
    "historical_max_volume", "Maximum_Monthly_Liters",
    "incremental_volume", "Trade_Spend_LKR", "Spend_Type",
]
_ = alloc_df[cols].to_csv(out_path, index=False)
print(f"\n[4/5] → Saved {out_path} ({len(alloc_df)} rows)")

simple_path = os.path.join(OUT_DIR, "ctrl_freaks_budget_allocations.csv")
_ = alloc_df[["Outlet_ID", "Trade_Spend_LKR"]].to_csv(simple_path, index=False)
print(f"      → Saved {simple_path} ({len(alloc_df)} rows)")

print("\n" + "=" * 60)
print("ALLOCATION SUMMARY")
print("=" * 60)
print(f"  Budget:              LKR {BUDGET:,.0f}")
print(f"  Total spend:         LKR {total_spend:,.0f}")
print(f"  Outlets funded:      {len(alloc_df)}")
if len(alloc_df) > 0:
    print(f"  Avg spend/outlet:    LKR {total_spend / len(alloc_df):,.0f}")
print(f"  Remaining:           LKR {remaining:,.0f}")
print("Done!")
