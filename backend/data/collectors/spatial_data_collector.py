import requests
import pandas as pd
import geopandas as gpd
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import time
import os
from pathlib import Path
from geoalchemy2 import Geometry
from geoalchemy2.shape import WKTElement
from sqlalchemy import create_engine, text
from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)

class SpatialDataCollector:
    """Collector for spatial data from NSW Government sources"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize the spatial data collector"""
        self.config = self._load_config(config_path)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NSW-Spatial-Data-Collector/1.0',
            'Accept': 'application/json'
        })
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as file:
                import yaml
                return yaml.safe_load(file)
        except FileNotFoundError:
            logger.error(f"Config file {config_path} not found")
            raise
    
    def collect_sa2_boundaries(self, shapefile_path: str) -> gpd.GeoDataFrame:
        """Collect SA2 boundaries from ABS shapefile"""
        try:
            # Load SA2 boundaries from ABS shapefile
            sa2_gdf = gpd.read_file(shapefile_path)
            
            # Clean and filter for Greater Sydney
            sa2_gdf = sa2_gdf[sa2_gdf['geometry'].notna()].copy()
            sa2_gdf = sa2_gdf.dropna(subset=['GCC_NAME21', 'SA2_CODE21', 'SA2_NAME21', 'SA4_NAME21', 'AREASQKM21'])
            sa2_gdf = sa2_gdf[sa2_gdf['GCC_NAME21'] == 'Greater Sydney'].copy()
            sa2_gdf = sa2_gdf.to_crs('EPSG:4326')
            
            # Select and rename columns
            sa2_gdf = sa2_gdf[[
                'SA2_CODE21',
                'SA2_NAME21',
                'SA4_NAME21',
                'AREASQKM21',
                'geometry'
            ]].rename(columns={
                'SA2_CODE21': 'sa2_code',
                'SA2_NAME21': 'sa2_name',
                'SA4_NAME21': 'sa4_name',
                'AREASQKM21': 'area_sqkm'
            })
            
            logger.info(f"Loaded {len(sa2_gdf)} SA2 regions for Greater Sydney")
            return sa2_gdf
            
        except Exception as e:
            logger.error(f"Error loading SA2 boundaries: {e}")
            raise
    
    def collect_pois_from_api(self, min_lat: float, min_lon: float, 
                             max_lat: float, max_lon: float) -> List[Dict]:
        """Collect Points of Interest from NSW POI API within bounding box"""
        base_url = "https://maps.six.nsw.gov.au/arcgis/rest/services/public/NSW_POI/MapServer/0/query"
        
        params = {
            'f': 'json',
            'geometry': f"{min_lon},{min_lat},{max_lon},{max_lat}",
            'geometryType': 'esriGeometryEnvelope',
            'spatialRel': 'esriSpatialRelIntersects',
            'outFields': '*',
            'returnGeometry': 'true',
            'inSR': '4326',
            'outSR': '4326',
            'maxRecordCount': 1000
        }
        
        try:
            response = self.session.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'features' in data:
                features = data['features']
                processed_pois = []
                
                for feature in features:
                    poi = feature['attributes']
                    if 'geometry' in feature:
                        poi['longitude'] = feature['geometry'].get('x')
                        poi['latitude'] = feature['geometry'].get('y')
                    processed_pois.append(poi)
                
                logger.info(f"Found {len(processed_pois)} POIs in bounding box")
                return processed_pois
            else:
                logger.warning("No features found in POI API response")
                return []
                
        except Exception as e:
            logger.error(f"Error collecting POIs: {e}")
            return []
    
    def collect_pois_for_sa2_regions(self, db_engine, sa4_codes: List[str] = None) -> List[Dict]:
        """Collect POIs for specific SA2 regions using spatial queries"""
        if sa4_codes is None:
            sa4_codes = ['117', '125', '126']  # Sydney City, Parramatta, Ryde
        
        try:
            # Get SA2 regions from database
            query = """
                SELECT 
                    sa2_code,
                    sa2_name,
                    ST_AsText(geometry) as geom,
                    ST_XMin(geometry) as min_lon,
                    ST_YMin(geometry) as min_lat,
                    ST_XMax(geometry) as max_lon,
                    ST_YMax(geometry) as max_lat
                FROM sa2_boundaries
                WHERE substring(sa2_code from 1 for 3) = ANY(%s)
            """
            
            with db_engine.connect() as conn:
                result = conn.execute(text(query), sa4_codes)
                sa2_regions = []
                for row in result:
                    sa2_regions.append({
                        'sa2_code': row[0],
                        'sa2_name': row[1],
                        'geometry': row[2],
                        'min_lon': float(row[3]),
                        'min_lat': float(row[4]),
                        'max_lon': float(row[5]),
                        'max_lat': float(row[6])
                    })
            
            logger.info(f"Found {len(sa2_regions)} SA2 regions")
            
            all_pois = []
            for i, region in enumerate(sa2_regions, 1):
                logger.info(f"Processing region {i}/{len(sa2_regions)}: {region['sa2_name']}")
                
                # Get POIs within bounding box
                pois = self.collect_pois_from_api(
                    region['min_lat'],
                    region['min_lon'],
                    region['max_lat'],
                    region['max_lon']
                )
                
                if pois:
                    # Filter POIs using PostGIS to ensure they're within SA2 boundary
                    longitudes = [p['longitude'] for p in pois]
                    latitudes = [p['latitude'] for p in pois]
                    
                    filter_query = """
                        WITH poi_points AS (
                            SELECT ST_SetSRID(ST_Point(lon, lat), 4326) as geom
                            FROM unnest(%s::float[], %s::float[]) AS t(lon, lat)
                        )
                        SELECT ST_Contains(ST_GeomFromText(%s, 4326), geom) as is_contained
                        FROM poi_points
                    """
                    
                    with db_engine.connect() as conn:
                        result = conn.execute(text(filter_query), 
                                            longitudes, latitudes, region['geometry'])
                        contained = [row[0] for row in result]
                    
                    # Add SA2 information to contained POIs
                    filtered_pois = []
                    for poi, is_contained in zip(pois, contained):
                        if is_contained:
                            poi['sa2_code'] = region['sa2_code']
                            poi['sa2_name'] = region['sa2_name']
                            filtered_pois.append(poi)
                    
                    logger.info(f"Found {len(filtered_pois)} POIs within SA2 boundary")
                    all_pois.extend(filtered_pois)
                
                time.sleep(1)  # Rate limiting
            
            logger.info(f"Total POIs collected: {len(all_pois)}")
            return all_pois
            
        except Exception as e:
            logger.error(f"Error collecting POIs for SA2 regions: {e}")
            return []
    
    def collect_transport_stops(self, gtfs_path: str) -> pd.DataFrame:
        """Collect transport stops from GTFS data"""
        try:
            stops_path = os.path.join(gtfs_path, "stops.txt")
            df = pd.read_csv(stops_path)
            
            # Clean and process data
            df['platform_code'] = pd.to_numeric(df['platform_code'], errors='coerce').fillna(0).astype(int)
            df['parent_station'] = pd.to_numeric(df['parent_station'], errors='coerce').fillna(0).astype(int)
            df['location_type'] = pd.to_numeric(df['location_type'], errors='coerce').fillna(0).astype(int)
            df['stop_code'] = pd.to_numeric(df['stop_code'], errors='coerce').fillna(0).astype(int)
            df['wheelchair_boarding'] = pd.to_numeric(df['wheelchair_boarding'], errors='coerce').fillna(0).astype(int)
            df['stop_lat'] = pd.to_numeric(df['stop_lat'], errors='coerce')
            df['stop_lon'] = pd.to_numeric(df['stop_lon'], errors='coerce')
            
            # Create geometry column
            df['geometry'] = gpd.points_from_xy(df.stop_lon, df.stop_lat)
            df['geom'] = df['geometry'].apply(lambda x: WKTElement(x.wkt, srid=4326))
            
            df.drop_duplicates(inplace=True)
            df.dropna(inplace=True)
            df = df.drop(columns=['geometry'])
            
            logger.info(f"Loaded {len(df)} transport stops")
            return df
            
        except Exception as e:
            logger.error(f"Error loading transport stops: {e}")
            raise
    
    def collect_school_catchments(self, catchments_path: str) -> pd.DataFrame:
        """Collect school catchment data from shapefiles"""
        try:
            shapefiles = {
                "primary": "catchments_primary.shp",
                "secondary": "catchments_secondary.shp",
                "future": "catchments_future.shp"
            }
            
            dataframes = []
            for name, shapefile in shapefiles.items():
                file_path = os.path.join(catchments_path, shapefile)
                if os.path.exists(file_path):
                    df = gpd.read_file(file_path)
                    dataframes.append(df)
                else:
                    logger.warning(f"Shapefile {shapefile} not found at {file_path}")
            
            if not dataframes:
                raise FileNotFoundError("No shapefiles found in the specified directory")
            
            df = pd.concat(dataframes, ignore_index=True)
            df = df.drop_duplicates(subset=['USE_ID'], keep='first')
            
            # Convert geometry
            df['geom'] = df['geometry'].apply(lambda x: WKTElement(x.wkt, srid=4326))
            df = df.drop(columns='geometry')
            
            # Process boolean columns
            bool_columns = ['KINDERGART', 'YEAR1', 'YEAR2', 'YEAR3', 'YEAR4', 'YEAR5', 
                           'YEAR6', 'YEAR7', 'YEAR8', 'YEAR9', 'YEAR10', 'YEAR11', 
                           'YEAR12', 'PRIORITY']
            
            for col in bool_columns:
                if col in df.columns:
                    df[col] = df[col].fillna('N')
                    df[col] = df[col].map({'Y': 1, 'N': 0})
            
            df['USE_ID'] = df['USE_ID'].astype(int)
            df.columns = df.columns.str.lower()
            
            logger.info(f"Loaded {len(df)} school catchment records")
            return df
            
        except Exception as e:
            logger.error(f"Error loading school catchments: {e}")
            raise
    
    def collect_business_data(self, csv_path: str) -> pd.DataFrame:
        """Collect business data from CSV file"""
        try:
            df = pd.read_csv(csv_path)
            
            # Rename columns to match database schema
            df = df.rename(columns={
                '0_to_50k_businesses': 'businesses_0_to_50k',
                '50k_to_200k_businesses': 'businesses_50k_to_200k',
                '200k_to_2m_businesses': 'businesses_200k_to_2m',
                '2m_to_5m_businesses': 'businesses_2m_to_5m',
                '5m_to_10m_businesses': 'businesses_5m_to_10m',
                '10m_or_more_businesses': 'businesses_10m_or_more'
            })
            
            logger.info(f"Loaded {len(df)} business records")
            return df
            
        except Exception as e:
            logger.error(f"Error loading business data: {e}")
            raise
    
    def collect_population_data(self, csv_path: str) -> pd.DataFrame:
        """Collect population data from CSV file"""
        try:
            df = pd.read_csv(csv_path)
            
            # Clean data
            df.drop_duplicates(inplace=True)
            df.dropna(inplace=True)
            df = df[df['total_people'] != 0]
            
            logger.info(f"Loaded {len(df)} population records")
            return df
            
        except Exception as e:
            logger.error(f"Error loading population data: {e}")
            raise
    
    def collect_income_data(self, csv_path: str) -> pd.DataFrame:
        """Collect income data from CSV file"""
        try:
            df = pd.read_csv(csv_path)
            
            # Clean data
            df.drop_duplicates(inplace=True)
            df.dropna(inplace=True)
            df.replace('np', 0, inplace=True)
            df = df.rename(columns={'sa2_code21': 'sa2_code'})
            
            logger.info(f"Loaded {len(df)} income records")
            return df
            
        except Exception as e:
            logger.error(f"Error loading income data: {e}")
            raise 