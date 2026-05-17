import pandas as pd
import os
import yaml
from zenml import step

@step(experiment_tracker="mlflow_tracker")
def clean_silver(bronze_counts: dict) -> dict:
    """Cleans transactions and quarantines bad data."""
    import mlflow # Import here for ZenML compatibility
    
    with open("params.yaml", "r") as f:
        params = yaml.safe_load(f)
        
    bronze_dir = params['data']['bronze_dir']
    silver_dir = params['data']['silver_dir']
    rejected_dir = os.path.join(silver_dir, "rejected")
    
    # Example for Transactions (Add logic for other tables later)
    tx_path = os.path.join(bronze_dir, "transactions.parquet")
    
    if os.path.exists(tx_path):
        df = pd.read_parquet(tx_path)
        initial_rows = len(df)
        
        # 1. Check Nulls
        from pipeline.dq_checks import check_nulls, quarantine
        bad_nulls = check_nulls(df, ['Outlet_ID', 'Volume_Liters'], 'transactions')
        df = quarantine(df, bad_nulls, 'null_mandatory_fields', rejected_dir, 'transactions')
        
        # 2. Check Negative Volumes
        bad_negatives = df[df['Volume_Liters'] < params['cleaning']['min_volume_liters']].copy()
        df = quarantine(df, bad_negatives, 'negative_volume', rejected_dir, 'transactions')
        
        # Save Clean Silver
        df.to_parquet(os.path.join(silver_dir, "transactions_clean.parquet"), index=False)
        
        clean_rows = len(df)
        
        # Log to MLflow
        mlflow.log_metric("dq_total_raw_rows", initial_rows)
        mlflow.log_metric("dq_clean_rows", clean_rows)
        mlflow.log_metric("dq_clean_ratio", clean_rows / initial_rows if initial_rows > 0 else 0)
        
        print(f"[Silver] Cleaned transactions: {clean_rows}/{initial_rows} rows retained.")
        
    return {"status": "Silver layer complete"}