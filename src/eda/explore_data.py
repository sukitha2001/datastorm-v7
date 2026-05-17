import pandas as pd
import os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 60)
print("MASTER TRAINING DATA (Gold)")
print("=" * 60)
master = pd.read_parquet(os.path.join(BASE, "data/gold/master_training_data.parquet"))
print(f"Shape: {master.shape}")
print(f"Columns: {list(master.columns)}")
print(master.dtypes)
print()
print(master.describe().to_string())
print()
print(master.head(3).to_string())

print("\n" + "=" * 60)
print("SPATIAL FEATURES (Gold)")
print("=" * 60)
spatial = pd.read_parquet(os.path.join(BASE, "data/gold/spatial_features.parquet"))
print(f"Shape: {spatial.shape}")
print(f"Columns: {list(spatial.columns)}")
print(spatial.describe().to_string())

print("\n" + "=" * 60)
print("BRONZE COORDINATES")
print("=" * 60)
coords = pd.read_parquet(os.path.join(BASE, "data/bronze/coordinates.parquet"))
print(f"Shape: {coords.shape}")
print(f"Columns: {list(coords.columns)}")
print(coords.head(5).to_string())

print("\n" + "=" * 60)
print("BRONZE OUTLET MASTER")
print("=" * 60)
outlets = pd.read_parquet(os.path.join(BASE, "data/bronze/outlet_master.parquet"))
print(f"Shape: {outlets.shape}")
print(f"Columns: {list(outlets.columns)}")
print(outlets.head(5).to_string())
print()
print("Unique outlet types:", outlets.columns.tolist())
# Check for outlet type column
for col in outlets.columns:
    if outlets[col].dtype == 'object':
        nunique = outlets[col].nunique()
        if nunique < 30:
            print(f"  {col}: {nunique} unique => {outlets[col].value_counts().head(10).to_dict()}")

print("\n" + "=" * 60)
print("BRONZE TRANSACTIONS (sample)")
print("=" * 60)
tx = pd.read_parquet(os.path.join(BASE, "data/bronze/transactions.parquet"))
print(f"Shape: {tx.shape}")
print(f"Columns: {list(tx.columns)}")
print(tx.dtypes)
print(tx.head(5).to_string())

print("\n" + "=" * 60)
print("BRONZE SEASONALITY")
print("=" * 60)
seas = pd.read_parquet(os.path.join(BASE, "data/bronze/seasonality.parquet"))
print(f"Shape: {seas.shape}")
print(f"Columns: {list(seas.columns)}")
print(seas.to_string())

print("\n" + "=" * 60)
print("BRONZE HOLIDAYS")
print("=" * 60)
holidays = pd.read_parquet(os.path.join(BASE, "data/bronze/holidays.parquet"))
print(f"Shape: {holidays.shape}")
print(f"Columns: {list(holidays.columns)}")
print(holidays.to_string())
