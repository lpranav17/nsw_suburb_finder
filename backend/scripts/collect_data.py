#!/usr/bin/env python3
"""
Main script for NSW Open Data Collection
This script will collect data once and populate the database for Greater Sydney area
"""

import os
import sys
import logging
import time
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('nsw_data_collection.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def collect_pois_by_sa4():
    """Collect POIs from NSW API for specific SA4 regions within Greater Sydney GCC"""
    import requests
    import json
    from sqlalchemy import create_engine, text
    import yaml
    import pandas as pd
    
    print("Creating SA4-based POI collector for Greater Sydney GCC...")
    
    # Load config
    config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Setup database connection (prefer DATABASE_URL env var for cloud providers like Neon)
    database_url_env = os.getenv('DATABASE_URL')
    if database_url_env and database_url_env.strip():
        db_url = database_url_env
    else:
        db_config = config.get('database', {})
        db_url = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['name']}"
    engine = create_engine(db_url, echo=False)
    
    # Enable PostGIS
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.commit()
    
    # Create POI table with SA4 information
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS poi_data CASCADE"))
        conn.execute(text("""
            CREATE TABLE poi_data (
                id SERIAL PRIMARY KEY,
                poi_id INTEGER UNIQUE,
                name VARCHAR(255),
                poitype VARCHAR(50),
                poigroup INTEGER,
                group_name VARCHAR(50),
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                sa4_code VARCHAR(20),
                sa4_name VARCHAR(100),
                geom GEOMETRY(Point, 4326),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("CREATE INDEX poi_data_geom_idx ON poi_data USING GIST (geom)"))
        conn.execute(text("CREATE INDEX poi_data_sa4_idx ON poi_data (sa4_code)"))
        conn.commit()
    
    # Define SA4 regions within Greater Sydney GCC
    # These are the main SA4 regions that make up Greater Sydney
    sydney_sa4_regions = [
        {
            'code': '116', 'name': 'Sydney - City and Inner South',
            'bbox': {'min_lat': -33.95, 'min_lon': 151.1, 'max_lat': -33.85, 'max_lon': 151.25}
        },
        {
            'code': '117', 'name': 'Sydney - Eastern Suburbs',
            'bbox': {'min_lat': -33.95, 'min_lon': 151.15, 'max_lat': -33.85, 'max_lon': 151.35}
        },
        {
            'code': '118', 'name': 'Sydney - Inner South West',
            'bbox': {'min_lat': -34.0, 'min_lon': 150.9, 'max_lat': -33.9, 'max_lon': 151.1}
        },
        {
            'code': '119', 'name': 'Sydney - Inner West',
            'bbox': {'min_lat': -33.9, 'min_lon': 151.0, 'max_lat': -33.8, 'max_lon': 151.15}
        },
        {
            'code': '120', 'name': 'Sydney - North Sydney and Hornsby',
            'bbox': {'min_lat': -33.8, 'min_lon': 151.0, 'max_lat': -33.6, 'max_lon': 151.25}
        },
        {
            'code': '121', 'name': 'Sydney - Northern Beaches',
            'bbox': {'min_lat': -33.8, 'min_lon': 151.15, 'max_lat': -33.6, 'max_lon': 151.35}
        },
        {
            'code': '122', 'name': 'Sydney - Outer South West',
            'bbox': {'min_lat': -34.2, 'min_lon': 150.7, 'max_lat': -34.0, 'max_lon': 150.9}
        },
        {
            'code': '123', 'name': 'Sydney - Outer West and Blue Mountains',
            'bbox': {'min_lat': -33.8, 'min_lon': 150.5, 'max_lat': -33.6, 'max_lon': 151.0}
        },
        {
            'code': '124', 'name': 'Sydney - Parramatta',
            'bbox': {'min_lat': -33.9, 'min_lon': 150.8, 'max_lat': -33.7, 'max_lon': 151.0}
        },
        {
            'code': '125', 'name': 'Sydney - Ryde',
            'bbox': {'min_lat': -33.8, 'min_lon': 151.0, 'max_lat': -33.7, 'max_lon': 151.15}
        },
        {
            'code': '126', 'name': 'Sydney - South West',
            'bbox': {'min_lat': -34.0, 'min_lon': 150.8, 'max_lat': -33.8, 'max_lon': 151.0}
        },
        {
            'code': '127', 'name': 'Sydney - Sutherland',
            'bbox': {'min_lat': -34.1, 'min_lon': 150.9, 'max_lat': -33.9, 'max_lon': 151.2}
        }
    ]
    
    base_url = "https://maps.six.nsw.gov.au/arcgis/rest/services/public/NSW_POI/MapServer/0/query"
    
    group_names = {
        1: "Community", 2: "Education", 3: "Recreation",
        4: "Transport", 5: "Utility", 6: "Hydrography",
        7: "Landform", 8: "Place", 9: "Industry"
    }
    
    all_poi_records = []
    total_pois = 0
    
    print(f"Collecting POIs from {len(sydney_sa4_regions)} SA4 regions...")
    
    for i, region in enumerate(sydney_sa4_regions, 1):
        bbox = region['bbox']
        print(f"\nSA4 Region {i}/{len(sydney_sa4_regions)}: {region['name']} ({region['code']})")
        print(f"Bounding box: {bbox['min_lat']:.2f}, {bbox['min_lon']:.2f} to {bbox['max_lat']:.2f}, {bbox['max_lon']:.2f}")
        
        params = {
            'f': 'json',
            'geometry': f"{bbox['min_lon']},{bbox['min_lat']},{bbox['max_lon']},{bbox['max_lat']}",
            'geometryType': 'esriGeometryEnvelope',
            'spatialRel': 'esriSpatialRelIntersects',
            'outFields': '*',
            'returnGeometry': 'true',
            'inSR': '4326',
            'outSR': '4326',
            'maxRecordCount': 1000  # Maximum allowed by API
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if 'features' in data:
                features = data['features']
                area_pois = 0
                
                for feature in features:
                    poi = feature['attributes']
                    if 'geometry' in feature:
                        poi['longitude'] = feature['geometry'].get('x')
                        poi['latitude'] = feature['geometry'].get('y')
                    
                    object_id = poi.get('objectid')
                    if object_id is None:
                        continue
                    
                    # Check if we already have this POI (avoid duplicates)
                    if not any(record['poi_id'] == object_id for record in all_poi_records):
                        all_poi_records.append({
                            'poi_id': object_id,
                            'name': poi.get('poiname', ''),
                            'poitype': poi.get('poitype', ''),
                            'poigroup': poi.get('poigroup'),
                            'group_name': group_names.get(poi.get('poigroup'), 'Unknown'),
                            'latitude': poi.get('latitude'),
                            'longitude': poi.get('longitude'),
                            'sa4_code': region['code'],
                            'sa4_name': region['name'],
                            'geom': f"SRID=4326;POINT({poi.get('longitude')} {poi.get('latitude')})"
                        })
                        area_pois += 1
                
                print(f"  Found {len(features)} POIs, {area_pois} new unique POIs")
                total_pois += area_pois
            else:
                print(f"  No features found in this SA4 region")
            
            # Small delay to be respectful to the API
            time.sleep(1)
            
        except Exception as e:
            print(f"  Error collecting POIs for {region['name']}: {e}")
            continue
    
    # Insert all POIs into database
    if all_poi_records:
        print(f"\nInserting {len(all_poi_records)} unique POIs into database...")
        df = pd.DataFrame(all_poi_records)
        df.to_sql('poi_data', engine, if_exists='append', index=False, method='multi')
        
        print(f"Successfully stored {len(all_poi_records)} POIs in database")
        
        # Show summary by SA4 region
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT sa4_name, COUNT(*) 
                FROM poi_data 
                GROUP BY sa4_name 
                ORDER BY COUNT(*) DESC
            """))
            print("\nPOIs by SA4 region:")
            for sa4_name, count in result:
                print(f"  - {sa4_name}: {count}")
            
            # Show summary by category
            result = conn.execute(text("""
                SELECT group_name, COUNT(*) 
                FROM poi_data 
                GROUP BY group_name 
                ORDER BY COUNT(*) DESC
            """))
            print("\nPOIs by category:")
            for group, count in result:
                print(f"  - {group}: {count}")
    else:
        print("No valid POIs found")
        return False
    
    return True

def main():
    """Main function to run the data collection"""
    print("NSW Open Data Collection - SA4 Regions")
    print("=" * 50)
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Collect POIs by SA4 regions
        success = collect_pois_by_sa4()
        
        if success:
            print("\n" + "=" * 50)
            print("Data collection completed!")
            print("\nDatabase tables created:")
            print("  - poi_data (POIs organized by SA4 regions)")
            
            print("\nNext steps:")
            print("1. Create a web application for SA4 region recommendations")
            print("2. Add more data sources (businesses, transport, etc.)")
            print("3. Implement user preference scoring system")
            
            print("\nTo build the web application, run:")
            print("  python create_web_app.py")
        else:
            print("\nData collection failed")
            
    except ImportError as e:
        logger.error(f"Import error: {e}")
        print(f"\nImport error: {e}")
        print("Make sure all required packages are installed:")
        print("  pip install -r requirements.txt")
        
    except Exception as e:
        logger.error(f"Error during data collection: {e}")
        print(f"\nError: {e}")
        print("Check the log file 'nsw_data_collection.log' for details")

if __name__ == "__main__":
    main() 