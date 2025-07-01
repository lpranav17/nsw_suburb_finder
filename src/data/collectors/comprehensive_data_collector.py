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
import yaml

logger = logging.getLogger(__name__)

class ComprehensiveDataCollector:
    """Comprehensive data collector for all SA2 regions in GCC - fetches once and stores permanently"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize the comprehensive data collector"""
        self.config = self._load_config(config_path)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NSW-Comprehensive-Data-Collector/1.0',
            'Accept': 'application/json'
        })
        self.db_engine = None
        self._setup_database()
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            logger.error(f"Config file {config_path} not found")
            raise
    
    def _setup_database(self):
        """Setup database connection"""
        db_config = self.config.get('database', {})
        db_url = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['name']}"
        self.db_engine = create_engine(db_url, echo=False)
        
        # Enable PostGIS extension
        with self.db_engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            conn.commit()
    
    def collect_all_data(self, data_sources: Dict[str, str]):
        """
        Collect all data once and store permanently in database
        data_sources: Dictionary with paths to data files
        """
        logger.info("Starting comprehensive data collection for all SA2 regions in GCC")
        
        try:
            # 1. Load and store SA2 boundaries for entire GCC
            self._load_sa2_boundaries(data_sources.get('sa2_shapefile'))
            
            # 2. Load and store business data
            self._load_business_data(data_sources.get('business_csv'))
            
            # 3. Load and store population data
            self._load_population_data(data_sources.get('population_csv'))
            
            # 4. Load and store income data
            self._load_income_data(data_sources.get('income_csv'))
            
            # 5. Load and store transport stops
            self._load_transport_stops(data_sources.get('gtfs_path'))
            
            # 6. Load and store school catchments
            self._load_school_catchments(data_sources.get('catchments_path'))
            
            # 7. Collect POIs for all SA2 regions (this takes time)
            self._collect_all_pois()
            
            # 8. Calculate and store well-resourced scores
            self._calculate_and_store_scores()
            
            logger.info("Comprehensive data collection completed successfully!")
            
        except Exception as e:
            logger.error(f"Error in comprehensive data collection: {e}")
            raise
    
    def _load_sa2_boundaries(self, shapefile_path: str):
        """Load SA2 boundaries for entire GCC region"""
        logger.info("Loading SA2 boundaries...")
        
        try:
            sa2_gdf = gpd.read_file(shapefile_path)
            sa2_gdf = sa2_gdf[sa2_gdf['geometry'].notna()].copy()
            sa2_gdf = sa2_gdf.dropna(subset=['GCC_NAME21', 'SA2_CODE21', 'SA2_NAME21', 'SA4_NAME21', 'AREASQKM21'])
            
 
            sa2_gdf = sa2_gdf[sa2_gdf['GCC_NAME21'] == 'Greater Sydney'].copy()
            sa2_gdf = sa2_gdf.to_crs('EPSG:4326')
            
            # Select and rename columns
            sa2_gdf = sa2_gdf[[
                'SA2_CODE21', 'SA2_NAME21', 'SA4_NAME21', 'GCC_NAME21', 'AREASQKM21', 'geometry'
            ]].rename(columns={
                'SA2_CODE21': 'sa2_code',
                'SA2_NAME21': 'sa2_name',
                'SA4_NAME21': 'sa4_name',
                'GCC_NAME21': 'gcc_name',
                'AREASQKM21': 'area_sqkm'
            })
            
            # Create table and store data
            with self.db_engine.connect() as conn:
                conn.execute(text("DROP TABLE IF EXISTS sa2_boundaries CASCADE"))
                conn.execute(text("""
                    CREATE TABLE sa2_boundaries (
                        sa2_code VARCHAR(10) PRIMARY KEY,
                        sa2_name VARCHAR(100),
                        sa4_name VARCHAR(100),
                        gcc_name VARCHAR(100),
                        area_sqkm FLOAT,
                        geometry geometry(MULTIPOLYGON, 4326)
                    )
                """))
                conn.execute(text("CREATE INDEX sa2_geom_idx ON sa2_boundaries USING GIST (geometry)"))
                conn.commit()
            
            sa2_gdf.to_postgis('sa2_boundaries', self.db_engine, if_exists='append', index=False)
            logger.info(f"Loaded {len(sa2_gdf)} SA2 regions across all GCC areas")
            
        except Exception as e:
            logger.error(f"Error loading SA2 boundaries: {e}")
            raise
    
    def _load_business_data(self, csv_path: str):
        """Load business data"""
        logger.info("Loading business data...")
        
        try:
            df = pd.read_csv(csv_path)
            df = df.rename(columns={
                '0_to_50k_businesses': 'businesses_0_to_50k',
                '50k_to_200k_businesses': 'businesses_50k_to_200k',
                '200k_to_2m_businesses': 'businesses_200k_to_2m',
                '2m_to_5m_businesses': 'businesses_2m_to_5m',
                '5m_to_10m_businesses': 'businesses_5m_to_10m',
                '10m_or_more_businesses': 'businesses_10m_or_more'
            })
            
            with self.db_engine.connect() as conn:
                conn.execute(text("DROP TABLE IF EXISTS businesses CASCADE"))
                conn.execute(text("""
                    CREATE TABLE businesses (
                        industry_code VARCHAR(5),
                        industry_name VARCHAR(100),
                        sa2_code VARCHAR(10),
                        sa2_name VARCHAR(100),
                        businesses_0_to_50k INTEGER,
                        businesses_50k_to_200k INTEGER,
                        businesses_200k_to_2m INTEGER,
                        businesses_2m_to_5m INTEGER,
                        businesses_5m_to_10m INTEGER,
                        businesses_10m_or_more INTEGER,
                        total_businesses INTEGER,
                        PRIMARY KEY (industry_code, sa2_code)
                    )
                """))
                conn.commit()
            
            df.to_sql('businesses', self.db_engine, if_exists='append', index=False)
            logger.info(f"Loaded {len(df)} business records")
            
        except Exception as e:
            logger.error(f"Error loading business data: {e}")
            raise
    
    def _load_population_data(self, csv_path: str):
        """Load population data"""
        logger.info("Loading population data...")
        
        try:
            df = pd.read_csv(csv_path)
            df.drop_duplicates(inplace=True)
            df.dropna(inplace=True)
            df = df[df['total_people'] != 0]
            
            with self.db_engine.connect() as conn:
                conn.execute(text("DROP TABLE IF EXISTS population CASCADE"))
                conn.execute(text("""
                    CREATE TABLE population (
                        sa2_code INTEGER,
                        sa2_name VARCHAR(255),
                        age_0_4 INTEGER,
                        age_5_9 INTEGER,
                        age_10_14 INTEGER,
                        age_15_19 INTEGER,
                        age_20_24 INTEGER,
                        age_25_29 INTEGER,
                        age_30_34 INTEGER,
                        age_35_39 INTEGER,
                        age_40_44 INTEGER,
                        age_45_49 INTEGER,
                        age_50_54 INTEGER,
                        age_55_59 INTEGER,
                        age_60_64 INTEGER,
                        age_65_69 INTEGER,
                        age_70_74 INTEGER,
                        age_75_79 INTEGER,
                        age_80_84 INTEGER,
                        age_85_plus INTEGER,
                        total_people INTEGER
                    )
                """))
                conn.commit()
            
            df.to_sql('population', self.db_engine, if_exists='append', index=False)
            logger.info(f"Loaded {len(df)} population records")
            
        except Exception as e:
            logger.error(f"Error loading population data: {e}")
            raise
    
    def _load_income_data(self, csv_path: str):
        """Load income data"""
        logger.info("Loading income data...")
        
        try:
            df = pd.read_csv(csv_path)
            df.drop_duplicates(inplace=True)
            df.dropna(inplace=True)
            df.replace('np', 0, inplace=True)
            df = df.rename(columns={'sa2_code21': 'sa2_code'})
            
            with self.db_engine.connect() as conn:
                conn.execute(text("DROP TABLE IF EXISTS income CASCADE"))
                conn.execute(text("""
                    CREATE TABLE income (
                        sa2_code VARCHAR(10),
                        sa2_name VARCHAR(100),
                        earners INTEGER,
                        median_age INTEGER,
                        median_income INTEGER,
                        mean_income INTEGER,
                        PRIMARY KEY (sa2_code)
                    )
                """))
                conn.commit()
            
            df.to_sql('income', self.db_engine, if_exists='append', index=False)
            logger.info(f"Loaded {len(df)} income records")
            
        except Exception as e:
            logger.error(f"Error loading income data: {e}")
            raise
    
    def _load_transport_stops(self, gtfs_path: str):
        """Load transport stops from GTFS data"""
        logger.info("Loading transport stops...")
        
        try:
            stops_path = os.path.join(gtfs_path, "stops.txt")
            df = pd.read_csv(stops_path)
            
            # Clean and process data
            numeric_columns = ['platform_code', 'parent_station', 'location_type', 
                              'stop_code', 'wheelchair_boarding', 'stop_lat', 'stop_lon']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # Create geometry column
            df['geometry'] = gpd.points_from_xy(df.stop_lon, df.stop_lat)
            df['geom'] = df['geometry'].apply(lambda x: WKTElement(x.wkt, srid=4326))
            
            df.drop_duplicates(inplace=True)
            df.dropna(inplace=True)
            df = df.drop(columns=['geometry'])
            
            with self.db_engine.connect() as conn:
                conn.execute(text("DROP TABLE IF EXISTS stops CASCADE"))
                conn.execute(text("""
                    CREATE TABLE stops (
                        stop_id VARCHAR(255),
                        stop_code INTEGER,
                        stop_name VARCHAR(255),
                        stop_lat FLOAT,
                        stop_lon FLOAT,
                        location_type INTEGER,
                        parent_station INTEGER,
                        wheelchair_boarding INTEGER,
                        platform_code INTEGER,
                        geom GEOMETRY(POINT, 4326),
                        PRIMARY KEY (stop_id)
                    )
                """))
                conn.commit()
            
            df.to_sql('stops', self.db_engine, if_exists='append', index=False)
            logger.info(f"Loaded {len(df)} transport stops")
            
        except Exception as e:
            logger.error(f"Error loading transport stops: {e}")
            raise
    
    def _load_school_catchments(self, catchments_path: str):
        """Load school catchment data"""
        logger.info("Loading school catchments...")
        
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
                logger.warning("No school catchment shapefiles found")
                return
            
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
            
            with self.db_engine.connect() as conn:
                conn.execute(text("DROP TABLE IF EXISTS schools CASCADE"))
                conn.execute(text("""
                    CREATE TABLE schools (
                        use_id INTEGER PRIMARY KEY,
                        catch_type VARCHAR(255),
                        use_desc VARCHAR(255),
                        add_date VARCHAR(255),
                        kindergart INTEGER,
                        year1 INTEGER,
                        year2 INTEGER,
                        year3 INTEGER,
                        year4 INTEGER,
                        year5 INTEGER,
                        year6 INTEGER,
                        year7 INTEGER,
                        year8 INTEGER,
                        year9 INTEGER,
                        year10 INTEGER,
                        year11 INTEGER,
                        year12 INTEGER,
                        priority INTEGER,
                        geom GEOMETRY(MULTIPOLYGON, 4326)
                    )
                """))
                conn.execute(text("CREATE INDEX schools_geom_idx ON schools USING GIST (geom)"))
                conn.commit()
            
            df.to_sql('schools', self.db_engine, if_exists='append', index=False)
            logger.info(f"Loaded {len(df)} school catchment records")
            
        except Exception as e:
            logger.error(f"Error loading school catchments: {e}")
            raise
    
    def _collect_all_pois(self):
        """Collect POIs for all SA2 regions - this is the most time-consuming part"""
        logger.info("Starting POI collection for all SA2 regions...")
        
        try:
            # Get all SA2 regions
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
                ORDER BY sa2_code
            """
            
            with self.db_engine.connect() as conn:
                result = conn.execute(text(query))
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
            
            logger.info(f"Found {len(sa2_regions)} SA2 regions for POI collection")
            
            # Create POI table
            with self.db_engine.connect() as conn:
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
                        sa2_code VARCHAR(20),
                        sa2_name VARCHAR(100),
                        geom GEOMETRY(Point, 4326),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text("CREATE INDEX poi_data_geom_idx ON poi_data USING GIST (geom)"))
                conn.commit()
            
            all_pois = []
            group_names = {
                1: "Community", 2: "Education", 3: "Recreation",
                4: "Transport", 5: "Utility", 6: "Hydrography",
                7: "Landform", 8: "Place", 9: "Industry"
            }
            
            for i, region in enumerate(sa2_regions, 1):
                logger.info(f"Processing region {i}/{len(sa2_regions)}: {region['sa2_name']}")
                
                # Get POIs within bounding box
                pois = self._get_pois_in_bbox(
                    region['min_lat'],
                    region['min_lon'],
                    region['max_lat'],
                    region['max_lon']
                )
                
                if pois:
                    # Filter POIs using PostGIS
                    filtered_pois = self._filter_pois_by_boundary(pois, region['geometry'])
                    
                    # Add SA2 information
                    for poi in filtered_pois:
                        poi['sa2_code'] = region['sa2_code']
                        poi['sa2_name'] = region['sa2_name']
                        poi['group_name'] = group_names.get(poi.get('poigroup'), 'Unknown')
                    
                    all_pois.extend(filtered_pois)
                    logger.info(f"Found {len(filtered_pois)} POIs within SA2 boundary")
                
                # Rate limiting
                time.sleep(0.5)
                
                # Batch insert every 1000 POIs
                if len(all_pois) >= 1000:
                    self._batch_insert_pois(all_pois)
                    all_pois = []
            
            # Insert remaining POIs
            if all_pois:
                self._batch_insert_pois(all_pois)
            
            logger.info("POI collection completed successfully!")
            
        except Exception as e:
            logger.error(f"Error collecting POIs: {e}")
            raise
    
    def _get_pois_in_bbox(self, min_lat: float, min_lon: float, 
                          max_lat: float, max_lon: float) -> List[Dict]:
        """Get POIs from NSW API within bounding box"""
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
                
                return processed_pois
            else:
                return []
                
        except Exception as e:
            logger.warning(f"Error getting POIs for bbox: {e}")
            return []
    
    def _filter_pois_by_boundary(self, pois: List[Dict], geometry_wkt: str) -> List[Dict]:
        """Filter POIs to ensure they're within SA2 boundary"""
        if not pois:
            return []
        
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
        
        with self.db_engine.connect() as conn:
            result = conn.execute(text(filter_query), 
                                longitudes, latitudes, geometry_wkt)
            contained = [row[0] for row in result]
        
        # Return only contained POIs
        filtered_pois = []
        for poi, is_contained in zip(pois, contained):
            if is_contained:
                filtered_pois.append(poi)
        
        return filtered_pois
    
    def _batch_insert_pois(self, pois: List[Dict]):
        """Batch insert POIs into database"""
        if not pois:
            return
        
        poi_data = []
        for poi in pois:
            object_id = poi.get('objectid')
            if object_id is None:
                continue
                
            poi_data.append((
                object_id,
                poi.get('poiname', ''),
                poi.get('poitype', ''),
                poi.get('poigroup'),
                poi.get('group_name', 'Unknown'),
                poi.get('latitude'),
                poi.get('longitude'),
                poi.get('sa2_code'),
                poi.get('sa2_name'),
                f"SRID=4326;POINT({poi.get('longitude')} {poi.get('latitude')})"
            ))
        
        if poi_data:
            with self.db_engine.connect() as conn:
                execute_values(conn, """
                    INSERT INTO poi_data (
                        poi_id, name, poitype, poigroup, group_name,
                        latitude, longitude, sa2_code, sa2_name, geom
                    )
                    VALUES %s
                    ON CONFLICT (poi_id) DO NOTHING
                """, poi_data)
                conn.commit()
    
    def _calculate_and_store_scores(self):
        """Calculate well-resourced scores for all SA2 regions"""
        logger.info("Calculating well-resourced scores...")
        
        try:
            from ..analysis.scoring_engine import WellResourcedScoringEngine
            
            scoring_engine = WellResourcedScoringEngine(self.db_engine)
            summary = scoring_engine.calculate_well_resourced_score()
            
            logger.info(f"Scoring completed. Processed {summary['total_regions']} regions")
            logger.info("Top 5 regions:")
            for region in summary['top_5_regions']:
                logger.info(f"  {region['name']}: {region['score']}")
            
        except Exception as e:
            logger.error(f"Error calculating scores: {e}")
            raise 