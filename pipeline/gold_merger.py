import pandas as pd
import os
from zenml import step

@step
def create_gold_master_table(
    transactions_path: str,
    outlet_master_path: str,
    spatial_feat_path: str,
    out_path: str
) -> pd.DataFrame:
    """Merges all layers into a single training-ready feature matrix."""
    
    # 1. Load data
    df_trans = pd.read_parquet(transactions_path)
    df_master = pd.read_parquet(outlet_master_path)
    df_spatial = pd.read_parquet(spatial_feat_path)
    
    print(f"[Gold] Merging features for {len(df_master)} outlets...")

    # 2. Aggregate Transactions
    df_trans_agg = df_trans.groupby('Outlet_ID').agg(
        total_historic_volume=('Volume_Liters', 'sum'),
        avg_transaction_size=('Volume_Liters', 'mean'),
        transaction_count=('Volume_Liters', 'count')
    ).reset_index()

    # 3. The Master Join
    final_df = df_master.merge(df_trans_agg, on='Outlet_ID', how='left')
    final_df = final_df.merge(df_spatial, on='Outlet_ID', how='left')
    
    # 4. SMART Data Imputation (The Fix)
    # Fill numeric columns with 0
    numeric_cols = final_df.select_dtypes(include=['number']).columns
    final_df[numeric_cols] = final_df[numeric_cols].fillna(0)
    
    # Fill object/string columns with "Unknown"
    object_cols = final_df.select_dtypes(include=['object']).columns
    final_df[object_cols] = final_df[object_cols].fillna("Unknown")
    
    # Force everything in object columns to be a string to satisfy PyArrow
    for col in object_cols:
        final_df[col] = final_df[col].astype(str)

    # 5. Save the final product
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    final_df.to_parquet(out_path, index=False)
    
    print(f"[Gold] Master Table Created: {final_df.shape[0]} rows, {final_df.shape[1]} features.")
    return final_df