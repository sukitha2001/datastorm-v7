import pandas as pd
import geopandas as gpd
import requests
import os
from shapely.geometry import Point
from zenml import step

import pandas as pd
import geopandas as gpd
import requests
import os
import time
from zenml import step

def download_sri_lanka_pois(out_path="scraping/sri_lanka_pois.parquet"):
    """Downloads all POIs for Sri Lanka with retries and a stable mirror."""
    
    if os.path.exists(out_path):
        print("[Explorer] Found local POI file. Skipping download.")
        return pd.read_parquet(out_path)

    # We use the Kumi Systems mirror - it's often more stable for big queries
    url = "https://overpass.kumi.systems/api/interpreter"
    
    bbox = "5.9,79.5,9.9,82.0"
    query = f"""
    [out:json][timeout:900];
    (
      node["amenity"~"school|hospital|bus_station|marketplace|restaurant|cafe|bar|hotel"]({bbox});
      node["shop"~"supermarket|convenience"]({bbox});
      node["tourism"="attraction"]({bbox});
    );
    out body;
    """

    for attempt in range(3): # Try up to 3 times
        try:
            print(f"[Explorer] Attempt {attempt+1}: Downloading master POI set...")
            # We give it 15 minutes (900s) to finish the big calculation
            response = requests.post(url, data={'data': query}, timeout=905)
            
            # If the server is busy, it might send a 429 or 504 error
            response.raise_for_status() 
            
            data = response.json()
            pois = []
            for el in data.get('elements', []):
                tags = el.get('tags', {})
                pois.append({
                    'poi_type': tags.get('amenity') or tags.get('shop') or tags.get('tourism'),
                    'lat': el['lat'], 'lon': el['lon']
                })
            
            df = pd.DataFrame(pois)
            df.to_parquet(out_path, index=False)
            print(f"[Explorer] Success! Saved {len(df)} points to {out_path}")
            return df

        except Exception as e:
            print(f"[Explorer] Attempt {attempt+1} failed: {e}")
            if attempt < 2:
                print("Waiting 30 seconds before trying again...")
                time.sleep(30)
            else:
                print("CRITICAL: All attempts to download map data failed.")
                raise

@step
def enrich_spatial_features(coords_path: str) -> pd.DataFrame:
    """Vectorized spatial join. Loads data from the provided path."""
    
    # Load the data INSIDE the step
    if not os.path.exists(coords_path):
        raise FileNotFoundError(f"Coordinates file not found at {coords_path}")
        
    outlet_coords_df = pd.read_parquet(coords_path)
    
    # 1. Get POIs (Using the function we wrote earlier)
    poi_df = download_sri_lanka_pois()
    
    # 2. Convert to GeoDataFrames
    gdf_outlets = gpd.GeoDataFrame(
        outlet_coords_df, 
        geometry=gpd.points_from_xy(outlet_coords_df.Longitude, outlet_coords_df.Latitude), 
        crs="EPSG:4326"
    )
    gdf_pois = gpd.GeoDataFrame(
        poi_df, 
        geometry=gpd.points_from_xy(poi_df.lon, poi_df.lat), 
        crs="EPSG:4326"
    )
    
    # 3. Project to UTM Zone 44N for metric buffering
    gdf_outlets = gdf_outlets.to_crs(epsg=32644)
    gdf_pois = gdf_pois.to_crs(epsg=32644)
    
    # 4. Create 1km buffers
    gdf_outlets['geometry'] = gdf_outlets.geometry.buffer(1000) 
    
    # 5. Spatial Join
    joined = gpd.sjoin(gdf_outlets, gdf_pois, how="left", predicate="intersects")
    
    # 6. Aggregate counts
    poi_counts = joined.groupby(['Outlet_ID', 'poi_type']).size().unstack(fill_value=0)
    poi_counts.columns = [f"poi_{c}_count" for c in poi_counts.columns]
    
    return poi_counts.reset_index()