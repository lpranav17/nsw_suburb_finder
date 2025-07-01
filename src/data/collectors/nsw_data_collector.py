import requests
import pandas as pd
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import time
import yaml
from pathlib import Path
import os

logger = logging.getLogger(__name__)

class NSWDataCollector:
    """Collector for NSW Government Open Data sources"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize the data collector with configuration"""
        self.config = self._load_config(config_path)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NSW-OpenData-Collector/1.0',
            'Accept': 'application/json'
        })
        self.data_sources = self.config.get('data_sources', {})
        self.collection_settings = self.config.get('data_collection', {})
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            logger.error(f"Config file {config_path} not found")
            raise
    
    def _make_request(self, url: str, params: Optional[Dict] = None, 
                     retries: int = 3) -> Optional[Dict]:
        """Make HTTP request with retry logic"""
        for attempt in range(retries):
            try:
                response = self.session.get(
                    url, 
                    params=params, 
                    timeout=self.collection_settings.get('timeout', 30)
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(self.collection_settings.get('retry_delay', 5))
                else:
                    logger.error(f"Request failed after {retries} attempts: {url}")
                    return None
    
    def collect_property_data(self, suburb: str = None, limit: int = 1000) -> List[Dict]:
        """Collect property data from NSW Planning Portal"""
        try:
            base_url = self.data_sources['planning_portal']['base_url']
            endpoint = self.data_sources['planning_portal']['endpoints']['property_info']
            url = f"{base_url}{endpoint}"
            
            params = {
                'limit': limit,
                'format': 'json'
            }
            if suburb:
                params['suburb'] = suburb
            
            data = self._make_request(url, params)
            if data:
                logger.info(f"Collected {len(data.get('features', []))} property records")
                return self._process_property_data(data.get('features', []))
            
            return []
            
        except Exception as e:
            logger.error(f"Error collecting property data: {e}")
            return []
    
    def collect_transport_data(self, suburb: str = None) -> List[Dict]:
        """Collect transport data from Transport for NSW"""
        try:
            base_url = self.data_sources['transport_nsw']['base_url']
            endpoints = self.data_sources['transport_nsw']['endpoints']
            
            transport_data = []
            
            # Collect routes data
            routes_url = f"{base_url}{endpoints['routes']}"
            routes_data = self._make_request(routes_url)
            if routes_data:
                transport_data.extend(self._process_transport_routes(routes_data))
            
            # Collect stops data
            stops_url = f"{base_url}{endpoints['stops']}"
            stops_data = self._make_request(stops_url)
            if stops_data:
                transport_data.extend(self._process_transport_stops(stops_data))
            
            logger.info(f"Collected {len(transport_data)} transport records")
            return transport_data
            
        except Exception as e:
            logger.error(f"Error collecting transport data: {e}")
            return []
    
    def collect_crime_data(self, suburb: str = None, year: int = None) -> List[Dict]:
        """Collect crime statistics from NSW Bureau of Crime Statistics"""
        try:
            base_url = self.data_sources['crime_statistics']['base_url']
            endpoint = self.data_sources['crime_statistics']['endpoints']['crime_data']
            url = f"{base_url}{endpoint}"
            
            # Note: BOCSAR data is typically downloaded as Excel/CSV files
            # This is a simplified example - actual implementation would need
            # to handle file downloads and parsing
            
            params = {
                'format': 'csv',
                'year': year or datetime.now().year
            }
            if suburb:
                params['suburb'] = suburb
            
            # For demonstration, we'll simulate data collection
            # In practice, you'd download and parse the actual files
            crime_data = self._simulate_crime_data(suburb, year)
            
            logger.info(f"Collected {len(crime_data)} crime records")
            return crime_data
            
        except Exception as e:
            logger.error(f"Error collecting crime data: {e}")
            return []
    
    def collect_education_data(self, suburb: str = None) -> List[Dict]:
        """Collect education data from NSW Department of Education"""
        try:
            base_url = self.data_sources['education']['base_url']
            endpoints = self.data_sources['education']['endpoints']
            
            education_data = []
            
            # Collect school performance data
            performance_url = f"{base_url}{endpoints['school_performance']}"
            performance_data = self._make_request(performance_url)
            if performance_data:
                education_data.extend(self._process_education_data(performance_data))
            
            # Collect enrollment data
            enrollment_url = f"{base_url}{endpoints['enrollment']}"
            enrollment_data = self._make_request(enrollment_url)
            if enrollment_data:
                education_data.extend(self._process_enrollment_data(enrollment_data))
            
            logger.info(f"Collected {len(education_data)} education records")
            return education_data
            
        except Exception as e:
            logger.error(f"Error collecting education data: {e}")
            return []
    
    def collect_health_data(self, suburb: str = None) -> List[Dict]:
        """Collect health facility data from NSW Health"""
        try:
            base_url = self.data_sources['health']['base_url']
            endpoints = self.data_sources['health']['endpoints']
            
            health_data = []
            
            # Collect facilities data
            facilities_url = f"{base_url}{endpoints['facilities']}"
            facilities_data = self._make_request(facilities_url)
            if facilities_data:
                health_data.extend(self._process_health_facilities(facilities_data))
            
            # Collect services data
            services_url = f"{base_url}{endpoints['services']}"
            services_data = self._make_request(services_url)
            if services_data:
                health_data.extend(self._process_health_services(services_data))
            
            logger.info(f"Collected {len(health_data)} health records")
            return health_data
            
        except Exception as e:
            logger.error(f"Error collecting health data: {e}")
            return []
    
    def collect_environment_data(self, suburb: str = None) -> List[Dict]:
        """Collect environmental data from NSW Environment"""
        try:
            base_url = self.data_sources['environment']['base_url']
            endpoints = self.data_sources['environment']['endpoints']
            
            environment_data = []
            
            # Collect parks data
            parks_url = f"{base_url}{endpoints['parks']}"
            parks_data = self._make_request(parks_url)
            if parks_data:
                environment_data.extend(self._process_parks_data(parks_data))
            
            # Collect recreation data
            recreation_url = f"{base_url}{endpoints['recreation']}"
            recreation_data = self._make_request(recreation_url)
            if recreation_data:
                environment_data.extend(self._process_recreation_data(recreation_data))
            
            logger.info(f"Collected {len(environment_data)} environment records")
            return environment_data
            
        except Exception as e:
            logger.error(f"Error collecting environment data: {e}")
            return []
    
    def _process_property_data(self, features: List[Dict]) -> List[Dict]:
        """Process raw property data into standardized format"""
        processed_data = []
        for feature in features:
            properties = feature.get('properties', {})
            geometry = feature.get('geometry', {})
            
            processed_data.append({
                'address': properties.get('address', ''),
                'property_type': properties.get('property_type', ''),
                'bedrooms': properties.get('bedrooms'),
                'bathrooms': properties.get('bathrooms'),
                'parking_spaces': properties.get('parking_spaces'),
                'land_size_m2': properties.get('land_size'),
                'floor_area_m2': properties.get('floor_area'),
                'price': properties.get('price'),
                'price_type': properties.get('price_type', ''),
                'sale_date': properties.get('sale_date'),
                'days_on_market': properties.get('days_on_market'),
                'agent': properties.get('agent', ''),
                'agency': properties.get('agency', ''),
                'features': properties.get('features', []),
                'latitude': geometry.get('coordinates', [None, None])[1],
                'longitude': geometry.get('coordinates', [None, None])[0],
                'metadata': properties
            })
        
        return processed_data
    
    def _process_transport_routes(self, data: Dict) -> List[Dict]:
        """Process transport routes data"""
        processed_data = []
        routes = data.get('routes', [])
        
        for route in routes:
            processed_data.append({
                'transport_type': route.get('transport_type', ''),
                'route_name': route.get('route_name', ''),
                'frequency_per_hour': route.get('frequency', 0),
                'first_service': route.get('first_service'),
                'last_service': route.get('last_service'),
                'wheelchair_accessible': route.get('wheelchair_accessible', False),
                'metadata': route
            })
        
        return processed_data
    
    def _process_transport_stops(self, data: Dict) -> List[Dict]:
        """Process transport stops data"""
        processed_data = []
        stops = data.get('stops', [])
        
        for stop in stops:
            processed_data.append({
                'station_name': stop.get('station_name', ''),
                'transport_type': stop.get('transport_type', ''),
                'latitude': stop.get('latitude'),
                'longitude': stop.get('longitude'),
                'parking_spaces': stop.get('parking_spaces', 0),
                'bike_racks': stop.get('bike_racks', 0),
                'wheelchair_accessible': stop.get('wheelchair_accessible', False),
                'metadata': stop
            })
        
        return processed_data
    
    def _simulate_crime_data(self, suburb: str, year: int) -> List[Dict]:
        """Simulate crime data for demonstration purposes"""
        crime_types = ['Assault', 'Theft', 'Burglary', 'Vehicle Theft', 'Fraud']
        location_types = ['residential', 'commercial', 'public']
        
        crime_data = []
        for crime_type in crime_types:
            for location_type in location_types:
                crime_data.append({
                    'crime_type': crime_type,
                    'year': year or datetime.now().year,
                    'month': 1,
                    'quarter': 1,
                    'incident_count': 10,  # Simulated data
                    'rate_per_100000': 50.0,  # Simulated data
                    'cleared_count': 5,  # Simulated data
                    'clearance_rate': 0.5,  # Simulated data
                    'severity_level': 'medium',
                    'location_type': location_type,
                    'metadata': {'simulated': True}
                })
        
        return crime_data
    
    def _process_education_data(self, data: Dict) -> List[Dict]:
        """Process education data"""
        processed_data = []
        schools = data.get('schools', [])
        
        for school in schools:
            processed_data.append({
                'school_name': school.get('school_name', ''),
                'school_type': school.get('school_type', ''),
                'sector': school.get('sector', ''),
                'naplan_score': school.get('naplan_score'),
                'hsc_performance': school.get('hsc_performance'),
                'enrollment_count': school.get('enrollment_count'),
                'teacher_student_ratio': school.get('teacher_student_ratio'),
                'facilities': school.get('facilities', []),
                'icsea_score': school.get('icsea_score'),
                'metadata': school
            })
        
        return processed_data
    
    def _process_enrollment_data(self, data: Dict) -> List[Dict]:
        """Process enrollment data"""
        # Similar processing logic for enrollment data
        return []
    
    def _process_health_facilities(self, data: Dict) -> List[Dict]:
        """Process health facilities data"""
        processed_data = []
        facilities = data.get('facilities', [])
        
        for facility in facilities:
            processed_data.append({
                'facility_name': facility.get('facility_name', ''),
                'facility_type': facility.get('facility_type', ''),
                'service_type': facility.get('services', []),
                'waiting_time_days': facility.get('waiting_time'),
                'rating': facility.get('rating'),
                'operating_hours': facility.get('operating_hours', ''),
                'emergency_services': facility.get('emergency_services', False),
                'bulk_billing': facility.get('bulk_billing', False),
                'wheelchair_accessible': facility.get('wheelchair_accessible', False),
                'metadata': facility
            })
        
        return processed_data
    
    def _process_health_services(self, data: Dict) -> List[Dict]:
        """Process health services data"""
        # Similar processing logic for health services
        return []
    
    def _process_parks_data(self, data: Dict) -> List[Dict]:
        """Process parks data"""
        processed_data = []
        parks = data.get('parks', [])
        
        for park in parks:
            processed_data.append({
                'amenity_type': 'park',
                'amenity_name': park.get('park_name', ''),
                'size_hectares': park.get('size_hectares'),
                'rating': park.get('rating'),
                'facilities': park.get('facilities', []),
                'opening_hours': park.get('opening_hours', ''),
                'accessibility_score': park.get('accessibility_score'),
                'metadata': park
            })
        
        return processed_data
    
    def _process_recreation_data(self, data: Dict) -> List[Dict]:
        """Process recreation data"""
        # Similar processing logic for recreation data
        return []
    
    def collect_all_data(self, suburb: str = None) -> Dict[str, List[Dict]]:
        """Collect data from all sources"""
        logger.info("Starting comprehensive data collection")
        
        all_data = {
            'properties': self.collect_property_data(suburb),
            'transport': self.collect_transport_data(suburb),
            'crime': self.collect_crime_data(suburb),
            'education': self.collect_education_data(suburb),
            'health': self.collect_health_data(suburb),
            'environment': self.collect_environment_data(suburb)
        }
        
        total_records = sum(len(data) for data in all_data.values())
        logger.info(f"Data collection completed. Total records: {total_records}")
        
        return all_data 