from zenml import pipeline, step
import pandas as pd
import yaml
import os

# Import the logic we've built in other files
from pipeline.bronze_ingestion import ingest_bronze
from pipeline.silver_cleaning import clean_silver
from scraping.poi_processor import enrich_spatial_features
from pipeline.gold_merger import create_gold_master_table

@step
def save_gold_features(df: pd.DataFrame, out_path: str) -> str:
    """Saves spatial features and returns the path for the next step."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_parquet(out_path, index=False)
    print(f"[Gold] Saved intermediate spatial features to {out_path}")
    return out_path

@pipeline
def datastorm_v7_pipeline():
    """
    Main MLOps Pipeline for DataStorm 7.0
    Follows the Medallion Architecture: Bronze -> Silver -> Gold
    """
    
    # 1. Load configuration from your YAML file
    with open("params.yaml", "r") as f:
        params = yaml.safe_load(f)
        
    raw_dir = params['data']['raw_dir']
    bronze_dir = params['data']['bronze_dir']
    silver_dir = params['data']['silver_dir']
    gold_dir = params['data']['gold_dir']

    # --- PHASE 1: BRONZE (Ingestion) ---
    # Ingests raw CSVs and converts them to Parquet format
    bronze_stats = ingest_bronze(
        raw_dir=raw_dir, 
        bronze_dir=bronze_dir
    )
    
    # --- PHASE 2: SILVER (Cleaning & DQ) ---
    # Performs Data Quality checks and quarantines "Dirty" data
    # We pass bronze_stats to create a dependency link in ZenML
    silver_stats = clean_silver(bronze_stats)
    
    # --- PHASE 3: GOLD (Spatial Enrichment) ---
    # Vectorsize spatial joins with OpenStreetMap POIs
    # We pass the path as a string to avoid Pydantic serialization issues
    coords_file_path = os.path.join(bronze_dir, "coordinates.parquet")
    spatial_df = enrich_spatial_features(coords_path=coords_file_path)
    
    # Save the spatial features and get the confirmed path
    spatial_feat_path = os.path.join(gold_dir, "spatial_features.parquet")
    saved_spatial_path = save_gold_features(spatial_df, out_path=spatial_feat_path)
    
    # --- PHASE 4: GOLD (Master Merger) ---
    # Forges the final training matrix: Internal + External Data
    master_table = create_gold_master_table(
        transactions_path=os.path.join(silver_dir, "transactions_clean.parquet"),
        outlet_master_path=os.path.join(bronze_dir, "outlet_master.parquet"),
        spatial_feat_path=saved_spatial_path,
        out_path=os.path.join(gold_dir, "master_training_data.parquet")
    )

if __name__ == "__main__":
    # Execute the pipeline
    datastorm_v7_pipeline()