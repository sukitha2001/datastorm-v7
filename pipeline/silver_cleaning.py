import json
import os
from datetime import datetime

import numpy as np
import pandas as pd
import yaml

# from typing import Optional


def load_params():
    with open("params.yaml") as f:
        return yaml.safe_load(f)


def quarantine(
    rejected_all: list,
    clean_df: pd.DataFrame,
    rejected_df: pd.DataFrame,
    check_name: str,
    source_dataset: str,
):
    if len(rejected_df) == 0:
        return clean_df
    rejected_df = rejected_df.copy()
    rejected_df["source_dataset"] = source_dataset
    rejected_df["check_name"] = check_name
    rejected_df["quarantined_at"] = datetime.now().isoformat()
    if "failure_reason" not in rejected_df.columns:
        rejected_df["failure_reason"] = check_name
    rejected_df["original_row"] = rejected_df.apply(
        lambda r: r.to_json(default_handler=str), axis=1
    )
    rejected_cols = [
        "source_dataset",
        "original_row",
        "check_name",
        "failure_reason",
        "quarantined_at",
    ]
    for c in rejected_cols:
        if c not in rejected_df.columns:
            rejected_df[c] = ""
    rejected_all.append(rejected_df[rejected_cols])
    clean_idx = clean_df.index.difference(rejected_df.index)
    return clean_df.loc[clean_idx].copy()


def check_sales(df: pd.DataFrame, params: dict, rejected_all: list) -> pd.DataFrame:
    from pipeline.dq_checks import check_nulls, check_outlier_zscore, check_range

    report = {}

    df, rej = check_nulls(df, ["Outlet_ID", "Volume_Liters", "Distributor_ID"])
    rejected_all.append(assign_rejected(rej, "null_check", "sales"))
    report["sales_null_check"] = {"passed": len(df), "rejected": len(rej)}

    vol_min = params["cleaning"]["min_volume_liters"]
    vol_max = params["cleaning"]["max_volume_liters"]
    df, rej = check_range(df, "Volume_Liters", vol_min, vol_max)
    rejected_all.append(assign_rejected(rej, "range_check", "sales"))
    report["sales_volume_range"] = {"passed": len(df), "rejected": len(rej)}

    df, rej = check_outlier_zscore(df, "Volume_Liters", threshold=3.5)
    rejected_all.append(assign_rejected(rej, "outlier_zscore_check", "sales"))
    report["sales_outlier_zscore"] = {"passed": len(df), "rejected": len(rej)}

    df_sorted = df.sort_values(["Outlet_ID", "Year", "Month"]).reset_index(drop=True)
    flatline_outlets = set()
    for outlet_id, grp in df_sorted.groupby("Outlet_ID"):
        vols = grp["Volume_Liters"].values
        if len(vols) < 6:
            continue
        for i in range(len(vols) - 6 + 1):
            if np.allclose(vols[i : i + 6], vols[i], rtol=1e-3, atol=1e-3):
                flatline_outlets.add(outlet_id)
                break
    df["flatline_flag"] = df["Outlet_ID"].isin(flatline_outlets).astype(int)
    report["sales_flatline"] = {
        "passed": len(df) - df["flatline_flag"].sum(),
        "rejected": int(df["flatline_flag"].sum()),
    }

    print(f"  Sales: {len(df)} clean, flatline outlets: {len(flatline_outlets)}")
    return df


def check_coordinates(df: pd.DataFrame, rejected_all: list) -> pd.DataFrame:
    from pipeline.dq_checks import check_nulls, check_range

    report = {}

    df, rej = check_nulls(df, ["Outlet_ID", "Latitude", "Longitude"])
    rejected_all.append(assign_rejected(rej, "null_check", "coordinates"))
    report["coords_null"] = {"passed": len(df), "rejected": len(rej)}

    df, rej = check_range(df, "Latitude", 5.9, 9.9)
    rejected_all.append(assign_rejected(rej, "range_check", "coordinates"))
    report["coords_lat_range"] = {"passed": len(df), "rejected": len(rej)}

    df, rej = check_range(df, "Longitude", 79.7, 81.9)
    rejected_all.append(assign_rejected(rej, "range_check", "coordinates"))
    report["coords_lon_range"] = {"passed": len(df), "rejected": len(rej)}

    zero_mask = (df["Latitude"] == 0.0) & (df["Longitude"] == 0.0)
    if zero_mask.any():
        rej = df[zero_mask].copy()
        rejected_all.append(assign_rejected(rej, "zero_gps_check", "coordinates"))
        df = df.loc[np.invert(zero_mask)].copy()
        report["coords_zero_gps"] = {
            "passed": len(df),
            "rejected": int(zero_mask.sum()),
        }

    print(f"  Coordinates: {len(df)} clean")
    return df


def check_outlets(
    df: pd.DataFrame, flatline_outlet_ids: set, rejected_all: list
) -> pd.DataFrame:
    from pipeline.dq_checks import check_format, check_nulls

    report = {}

    df, rej = check_nulls(df, ["Outlet_ID", "Outlet_Type"])
    rejected_all.append(assign_rejected(rej, "null_check", "outlets"))
    report["outlets_null"] = {"passed": len(df), "rejected": len(rej)}

    df, rej = check_format(df, "Outlet_ID", pattern=r"OUT_\d+")
    rejected_all.append(assign_rejected(rej, "format_check", "outlets"))
    report["outlets_format"] = {"passed": len(df), "rejected": len(rej)}

    df["constraint_flag"] = df["Outlet_ID"].isin(flatline_outlet_ids).astype(int)

    # Normalize casing
    df["Outlet_Size"] = df["Outlet_Size"].str.strip().str.replace("small", "Small", case=False)
    df["Outlet_Type"] = df["Outlet_Type"].str.strip().replace({
        "Bakry": "Bakery", "Grocry": "Grocery",
    })

    report["outlets_constraint_flag"] = {
        "flagged": int(df["constraint_flag"].sum()),
        "unflagged": int(df.shape[0] - df["constraint_flag"].sum()),
    }
    print(
        f"  Outlets: {len(df)} clean, {df['constraint_flag'].sum()} constraint-flagged"
    )
    return df


def check_seasonality(df: pd.DataFrame, rejected_all: list) -> pd.DataFrame:
    from pipeline.dq_checks import check_nulls, check_range

    report = {}

    df, rej = check_nulls(df, ["Distributor_ID", "Year", "Month", "Seasonality_Index"])
    rejected_all.append(assign_rejected(rej, "null_check", "seasonality"))
    report["seas_null"] = {"passed": len(df), "rejected": len(rej)}

    df, rej = check_range(df, "Month", 1, 12)
    rejected_all.append(assign_rejected(rej, "range_check", "seasonality"))
    report["seas_month_range"] = {"passed": len(df), "rejected": len(rej)}

    print(f"  Seasonality: {len(df)} clean")
    return df


def check_holidays(df: pd.DataFrame, rejected_all: list) -> pd.DataFrame:
    from pipeline.dq_checks import check_nulls

    report = {}

    df, rej = check_nulls(df, ["Date", "Holiday_Name"])
    rejected_all.append(assign_rejected(rej, "null_check", "holidays"))
    report["hol_null"] = {"passed": len(df), "rejected": len(rej)}

    print(f"  Holidays: {len(df)} clean")
    return df


SPEC_REJECT_COLS = [
    "source_dataset",
    "original_row",
    "check_name",
    "failure_reason",
    "quarantined_at",
]


def assign_rejected(
    rej_df: pd.DataFrame, check_name: str, source_dataset: str
) -> pd.DataFrame:
    if len(rej_df) == 0:
        return pd.DataFrame(columns=SPEC_REJECT_COLS)
    rej_df = rej_df.copy()
    rej_df["source_dataset"] = source_dataset
    rej_df["check_name"] = check_name
    rej_df["quarantined_at"] = datetime.now().isoformat()
    if "failure_reason" not in rej_df.columns:
        rej_df["failure_reason"] = check_name
    rej_df["original_row"] = rej_df.apply(
        lambda r: r.to_json(default_handler=str), axis=1
    )
    for c in SPEC_REJECT_COLS:
        if c not in rej_df.columns:
            rej_df[c] = ""
    return rej_df[SPEC_REJECT_COLS]


def clean_silver(bronze_dir: str, silver_dir: str, params: dict) -> dict:
    os.makedirs(silver_dir, exist_ok=True)
    rejected_all = []
    dq_report = {}

    dq_report = {}

    # --- Sales ---
    tx_path = os.path.join(bronze_dir, "transactions.parquet")
    if os.path.exists(tx_path):
        print("[Silver] Cleaning sales...")
        sales_df = check_sales(pd.read_parquet(tx_path), params, rejected_all)
        sales_df.to_parquet(os.path.join(silver_dir, "sales.parquet"), index=False)
        flatline_outlets = set(
            sales_df[sales_df["flatline_flag"] == 1]["Outlet_ID"].unique()
        )
        dq_report["sales"] = {
            "initial_rows": len(pd.read_parquet(tx_path)),
            "clean_rows": len(sales_df),
            "flatline_outlets": len(flatline_outlets),
        }
    else:
        print("[WARN] transactions.parquet not found — skipping sales")
        sales_df = pd.DataFrame()
        flatline_outlets = set()

    # --- Outlets ---
    outlet_path = os.path.join(bronze_dir, "outlet_master.parquet")
    if os.path.exists(outlet_path):
        print("[Silver] Cleaning outlets...")
        outlets_df = check_outlets(
            pd.read_parquet(outlet_path), flatline_outlets, rejected_all
        )
        outlets_df.to_parquet(os.path.join(silver_dir, "outlets.parquet"), index=False)
        dq_report["outlets"] = {
            "clean_rows": len(outlets_df),
            "constraint_flagged": int(outlets_df["constraint_flag"].sum()),
        }
    else:
        print("[WARN] outlet_master.parquet not found — skipping outlets")

    # --- Coordinates ---
    coords_path = os.path.join(bronze_dir, "coordinates.parquet")
    if os.path.exists(coords_path):
        print("[Silver] Cleaning coordinates...")
        coords_df = check_coordinates(pd.read_parquet(coords_path), rejected_all)
        coords_df.to_parquet(
            os.path.join(silver_dir, "coordinates.parquet"), index=False
        )
        dq_report["coordinates"] = {"clean_rows": len(coords_df)}
    else:
        print("[WARN] coordinates.parquet not found — skipping coordinates")

    # --- Seasonality ---
    seas_path = os.path.join(bronze_dir, "seasonality.parquet")
    if os.path.exists(seas_path):
        print("[Silver] Cleaning seasonality...")
        seas_df = check_seasonality(pd.read_parquet(seas_path), rejected_all)
        seas_df.to_parquet(os.path.join(silver_dir, "seasonality.parquet"), index=False)
        dq_report["seasonality"] = {"clean_rows": len(seas_df)}
    else:
        print("[WARN] seasonality.parquet not found — skipping seasonality")

    # --- Holidays ---
    hol_path = os.path.join(bronze_dir, "holidays.parquet")
    if os.path.exists(hol_path):
        print("[Silver] Cleaning holidays...")
        hol_df = check_holidays(pd.read_parquet(hol_path), rejected_all)
        hol_df.to_parquet(os.path.join(silver_dir, "holidays.parquet"), index=False)
        dq_report["holidays"] = {"clean_rows": len(hol_df)}
    else:
        print("[WARN] holidays.parquet not found — skipping holidays")

    # --- Write unified rejected_records ---
    if rejected_all:
        rejected_df = pd.concat(rejected_all, ignore_index=True)
        rejected_df.to_parquet(
            os.path.join(silver_dir, "rejected_records.parquet"), index=False
        )
        print(f"[Silver] Rejected records: {len(rejected_df)} total")
    else:
        print("[Silver] No rejected records.")

    # --- Write dq_report.json ---
    dq_path = os.path.join(silver_dir, "dq_report.json")
    with open(dq_path, "w") as f:
        json.dump(dq_report, f, indent=2)
    print(f"[Silver] DQ report written to {dq_path}")

    return {"status": "Silver layer complete", "dq_report": dq_report}


if __name__ == "__main__":
    params = load_params()
    clean_silver(
        bronze_dir=params["data"]["bronze_dir"],
        silver_dir=params["data"]["silver_dir"],
        params=params,
    )
