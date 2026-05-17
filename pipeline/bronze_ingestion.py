import pandas as pd
import os
from zenml import step

@step
def ingest_bronze(raw_dir: str, bronze_dir: str) -> dict:
    """Ingests ALL raw CSVs into the Bronze layer."""
    
    files_to_ingest = {
        "transactions": "transactions_history_final.csv",
        "outlet_master": "outlet_master.csv",
        "coordinates": "outlet_coordinates.csv", # Added this!
        "seasonality": "distributor_seasonality_details.csv",
        "holidays": "holiday_list.csv"
    }
    
    row_counts = {}
    
    for key, filename in files_to_ingest.items():
        file_path = os.path.join(raw_dir, filename)
        
        if not os.path.exists(file_path):
            print(f"Warning: {filename} not found in {raw_dir}. Skipping.")
            continue
            
        df = pd.read_csv(file_path)
        out_path = os.path.join(bronze_dir, f"{key}.parquet")
        df.to_parquet(out_path, index=False)
        
        row_counts[key] = len(df)
        print(f"[Bronze] Ingested {key}: {len(df)} rows.")
        
    return row_counts