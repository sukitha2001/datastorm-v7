import numpy as np
import pandas as pd


def check_nulls(
    df: pd.DataFrame, mandatory_cols: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    bad_mask = df[mandatory_cols].isnull().any(axis=1)
    clean = df.loc[np.invert(bad_mask)].copy()
    rejected = df.loc[bad_mask].copy()
    if len(rejected):
        rejected["check_name"] = "null_check"
        rejected["failure_reason"] = (
            f"Null values in mandatory columns: {mandatory_cols}"
        )
    return clean, rejected


def check_duplicates(
    df: pd.DataFrame, key_cols: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    dup_mask = df.duplicated(subset=key_cols, keep=False)
    clean = df.loc[np.invert(dup_mask)].copy()
    rejected = df.loc[dup_mask].copy()
    if len(rejected):
        rejected["check_name"] = "duplicate_check"
        rejected["failure_reason"] = f"Duplicate rows on key: {key_cols}"
    return clean, rejected


def check_referential(
    df: pd.DataFrame, fk_col: str, ref_df: pd.DataFrame, ref_col: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    valid_refs = set(ref_df[ref_col].unique())
    bad_mask = df[fk_col].isin(valid_refs).eq(False)
    clean = df.loc[np.invert(bad_mask)].copy()
    rejected = df.loc[bad_mask].copy()
    if len(rejected):
        rejected["check_name"] = "referential_check"
        invalid_vals = rejected[fk_col].unique().tolist()[:5]
        rejected["failure_reason"] = (
            f"Referential integrity fail on {fk_col}: values {invalid_vals} not in {ref_col}"
        )
    return clean, rejected


def check_range(
    df: pd.DataFrame, col: str, min_val: float, max_val: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    bad_mask = (df[col] < min_val) | (df[col] > max_val)
    clean = df.loc[np.invert(bad_mask)].copy()
    rejected = df.loc[bad_mask].copy()
    if len(rejected):
        rejected["check_name"] = "range_check"
        rejected["failure_reason"] = f"{col} outside range [{min_val}, {max_val}]"
    return clean, rejected


from typing import Optional

def check_format(
    df: pd.DataFrame,
    col: str,
    pattern: Optional[str] = None,
    expected_dtype: Optional[str] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    bad_mask = pd.Series([False] * len(df), index=df.index)
    reasons = []

    if pattern:
        col_bad = df[col].astype(str).str.match(pattern, na=True).eq(False)
        bad_mask = bad_mask | col_bad
        reasons.append(f"mismatches regex: {pattern}")

    if expected_dtype:
        try:
            pd.to_numeric(df[col], errors="raise")
        except (ValueError, TypeError):
            type_bad = pd.Series([True] * len(df), index=df.index)
        else:
            type_bad = pd.Series([False] * len(df), index=df.index)
        bad_mask = bad_mask | type_bad
        reasons.append(f"expected dtype: {expected_dtype}")

    clean = df.loc[np.invert(bad_mask)].copy()
    rejected = df.loc[bad_mask].copy()
    if len(rejected):
        rejected["check_name"] = "format_check"
        rejected["failure_reason"] = f"{col} format invalid: {'; '.join(reasons)}"
    return clean, rejected


def check_outlier_zscore(
    df: pd.DataFrame, col: str, threshold: float = 3.5
) -> tuple[pd.DataFrame, pd.DataFrame]:
    numeric = pd.to_numeric(df[col], errors="coerce")
    mean = float(np.nanmean(numeric))
    std = float(np.nanstd(numeric))
    if std == 0 or pd.isna(std):
        return df.copy(), pd.DataFrame()
    z_scores = (numeric - mean) / std
    bad_mask = z_scores.abs() > threshold
    clean = df.loc[np.invert(bad_mask)].copy()
    rejected = df.loc[bad_mask].copy()
    if len(rejected):
        rejected["check_name"] = "outlier_zscore_check"
        rejected["failure_reason"] = (
            f"{col} |z-score| > {threshold} (z={z_scores[bad_mask].values[:1].tolist()})"
        )
    return clean, rejected


def check_historical_flatline(
    df: pd.DataFrame,
    outlet_id_col: str = "Outlet_ID",
    volume_col: str = "Volume_Liters",
    month_col: str = "Month",
    n_months: int = 6,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df_sorted = df.sort_values([outlet_id_col, month_col]).copy()
    outlet_groups = df_sorted.groupby(outlet_id_col)[volume_col]
    flatline_outlets = set()
    for outlet_id, volumes in outlet_groups:
        vols = volumes.values
        if len(vols) < n_months:
            continue
        for i in range(len(vols) - n_months + 1):
            segment = vols[i : i + n_months]
            if np.allclose(segment, segment[0], rtol=1e-3, atol=1e-3):
                flatline_outlets.add(outlet_id)
                break
    bad_mask = df_sorted[outlet_id_col].isin(flatline_outlets)
    clean = df_sorted.loc[np.invert(bad_mask)].copy()
    rejected = df_sorted.loc[bad_mask].copy()
    if len(rejected):
        rejected["check_name"] = "historical_flatline_check"
        rejected["failure_reason"] = (
            f"{outlet_id_col} has {n_months}+ consecutive identical {volume_col} values"
        )
    return clean, rejected
