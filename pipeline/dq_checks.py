import pandas as pd
import os

def check_nulls(df: pd.DataFrame, mandatory_cols: list, dataset_name: str) -> pd.DataFrame:
    """Returns rows that have nulls in mandatory columns."""
    bad_mask = df[mandatory_cols].isnull().any(axis=1)
    bad_rows = df[bad_mask].copy()
    print(f"[DQ] {dataset_name}  {len(bad_rows)} rows failed null check.")
    return bad_rows

def quarantine(df: pd.DataFrame, bad_rows: pd.DataFrame, reason: str, rejected_dir: str, dataset_name: str) -> pd.DataFrame:
    """Saves bad rows to rejected folder and returns the clean DataFrame."""
    if len(bad_rows) > 0:
        bad_rows['failure_reason'] = reason
        out_path = os.path.join(rejected_dir, f"{dataset_name}_{reason}.parquet")
        bad_rows.to_parquet(out_path, index=False)
        
        # Keep only rows that are NOT in the bad_rows index
        clean_df = df.drop(bad_rows.index)
        return clean_df
    return df