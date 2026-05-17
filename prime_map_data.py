import sys
import os

# Add the project root to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.bronze.poi_processor import download_sri_lanka_pois

print("Starting prime_map_data.py")

# This will run the download and save it to 'scraping/sri_lanka_pois.parquet'
download_sri_lanka_pois()

print("prime_map_data.py completed")