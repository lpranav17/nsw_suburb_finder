#!/usr/bin/env python3
"""
Sydney Suburb Recommender - FastAPI Web Application
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import yaml
from sqlalchemy import create_engine, text
import pandas as pd
import json

# Load configuration
with open('../config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Setup database connection
db_config = config.get('database', {})
db_url = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['name']}"
engine = create_engine(db_url, echo=False)

app = FastAPI(
    title="Sydney Suburb Recommender",
    description="Find the best suburb in Sydney based on your preferences",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class PreferenceWeights(BaseModel):
    recreation: float = 0.25
    community: float = 0.25
    transport: float = 0.25
    education: float = 0.15
    utility: float = 0.10
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_km: Optional[float] = 5.0

class SuburbRecommendation(BaseModel):
    suburb_name: str
    score: float
    poi_counts: Dict[str, int]
    total_pois: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_km: Optional[float] = None

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sydney Suburb Recommender</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #2c3e50;
                text-align: center;
                margin-bottom: 30px;
            }
            .preferences {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .preference-group {
                background: #ecf0f1;
                padding: 20px;
                border-radius: 8px;
            }
            .preference-group h3 {
                margin-top: 0;
                color: #34495e;
            }
            label {
                display: block;
                margin-bottom: 10px;
                font-weight: bold;
            }
            input[type="range"] {
                width: 100%;
                margin-bottom: 10px;
            }
            .value-display {
                text-align: center;
                font-weight: bold;
                color: #27ae60;
            }
            button {
                background: #3498db;
                color: white;
                padding: 15px 30px;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                cursor: pointer;
                width: 100%;
                margin-top: 20px;
            }
            button:hover {
                background: #2980b9;
            }
            .results {
                margin-top: 30px;
                display: none;
            }
            .suburb-card {
                background: #f8f9fa;
                padding: 20px;
                margin: 10px 0;
                border-radius: 8px;
                border-left: 4px solid #3498db;
            }
            .suburb-name {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
            }
            .suburb-score {
                font-size: 24px;
                color: #27ae60;
                margin: 10px 0;
            }
            .poi-breakdown {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 10px;
                margin-top: 10px;
            }
            .poi-category {
                background: white;
                padding: 10px;
                border-radius: 5px;
                text-align: center;
            }
            .loading {
                text-align: center;
                padding: 20px;
                display: none;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏠 Sydney Suburb Recommender</h1>
            <p style="text-align: center; color: #7f8c8d; margin-bottom: 30px;">
                Find the best suburb in Sydney based on your preferences for amenities and facilities
            </p>
            
            <div class="location-section">
                <h3>📍 Choose Your Location</h3>
                <div class="map-container">
                    <div id="map" style="height: 300px; width: 100%; border-radius: 8px; margin-bottom: 15px;"></div>
                    <div class="location-controls">
                        <input type="text" id="location-search" placeholder="Search for a location..." style="width: 70%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; margin-right: 10px;">
                        <button onclick="searchLocation()" style="padding: 10px 15px; background: #27ae60; color: white; border: none; border-radius: 4px; cursor: pointer;">Search</button>
                        <button onclick="useCurrentLocation()" style="padding: 10px 15px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; margin-left: 10px;">Use My Location</button>
                    </div>
                    <div id="selected-location" style="margin-top: 10px; padding: 10px; background: #f8f9fa; border-radius: 4px; display: none;">
                        <strong>Selected:</strong> <span id="location-text"></span>
                        <br><strong>Radius:</strong> <span id="radius-text">5 km</span>
                        <button onclick="clearLocation()" style="float: right; padding: 5px 10px; background: #e74c3c; color: white; border: none; border-radius: 4px; cursor: pointer;">Clear</button>
                    </div>
                    <div id="radius-selector" style="margin-top: 15px; display: none;">
                        <label style="display: block; margin-bottom: 8px; font-weight: bold;">Search Radius: <span id="radius-value">5</span> km</label>
                        <input type="range" id="radius-slider" min="1" max="20" value="5" style="width: 100%; margin-bottom: 5px;" oninput="updateRadius()">
                        <div style="display: flex; justify-content: space-between; font-size: 12px; color: #7f8c8d;">
                            <span>1 km</span>
                            <span>5 km</span>
                            <span>10 km</span>
                            <span>15 km</span>
                            <span>20 km</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="preferences">
                <div class="preference-group">
                    <h3>🎾 Recreation & Sports</h3>
                    <label>Importance: <span class="value-display" id="recreation-value">25%</span></label>
                    <input type="range" id="recreation" min="0" max="100" value="25" oninput="updateValue('recreation')">
                    <p>Parks, sports facilities, beaches, entertainment venues</p>
                </div>
                
                <div class="preference-group">
                    <h3>🏘️ Community</h3>
                    <label>Importance: <span class="value-display" id="community-value">25%</span></label>
                    <input type="range" id="community" min="0" max="100" value="25" oninput="updateValue('community')">
                    <p>Community centers, libraries, cultural facilities</p>
                </div>
                
                <div class="preference-group">
                    <h3>🚌 Transport</h3>
                    <label>Importance: <span class="value-display" id="transport-value">25%</span></label>
                    <input type="range" id="transport" min="0" max="100" value="25" oninput="updateValue('transport')">
                    <p>Public transport, stations, accessibility</p>
                </div>
                
                <div class="preference-group">
                    <h3>🎓 Education</h3>
                    <label>Importance: <span class="value-display" id="education-value">15%</span></label>
                    <input type="range" id="education" min="0" max="100" value="15" oninput="updateValue('education')">
                    <p>Schools, universities, educational facilities</p>
                </div>
                
                <div class="preference-group">
                    <h3>⚡ Utilities</h3>
                    <label>Importance: <span class="value-display" id="utility-value">10%</span></label>
                    <input type="range" id="utility" min="0" max="100" value="10" oninput="updateValue('utility')">
                    <p>Essential services, utilities, infrastructure</p>
                </div>
            </div>
            
            <button onclick="getRecommendations()">Get Suburb Recommendations</button>
            
            <div class="loading" id="loading">
                <p>🔍 Analyzing suburbs based on your preferences...</p>
            </div>
            
            <div class="results" id="results">
                <h2>🏆 Top Suburb Recommendations</h2>
                <div id="recommendations"></div>
            </div>
        </div>

        <script>
            let map, marker, circle;
            let selectedLocation = null;
            let currentRadius = 5; // Default radius in km
            
            // Initialize OpenStreetMap with Leaflet
            function initMap() {
                // Sydney coordinates
                const sydney = [-33.8688, 151.2093];
                
                map = L.map('map').setView(sydney, 10);
                
                // Add OpenStreetMap tiles
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '© OpenStreetMap contributors'
                }).addTo(map);
                
                // Add click listener to map
                map.on('click', function(event) {
                    placeMarker(event.latlng);
                });
            }
            
            function placeMarker(location) {
                // Remove existing marker and circle
                if (marker) {
                    map.removeLayer(marker);
                }
                if (circle) {
                    map.removeLayer(circle);
                }
                
                // Add new marker
                marker = L.marker(location).addTo(map);
                
                // Add circle with current radius
                circle = L.circle(location, {
                    color: 'red',
                    fillColor: '#f03',
                    fillOpacity: 0.3,
                    radius: currentRadius * 1000 // Convert km to meters
                }).addTo(map);
                
                selectedLocation = {
                    lat: location.lat,
                    lng: location.lng
                };
                
                // Update display
                document.getElementById('selected-location').style.display = 'block';
                document.getElementById('radius-selector').style.display = 'block';
                document.getElementById('location-text').textContent = `${location.lat.toFixed(4)}, ${location.lng.toFixed(4)}`;
                document.getElementById('radius-text').textContent = `${currentRadius} km`;
                
                // Center map on marker
                map.setView(location);
            }
            
            function searchLocation() {
                const address = document.getElementById('location-search').value;
                
                // Use Nominatim (OpenStreetMap's geocoding service)
                fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}&limit=1`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.length > 0) {
                            const location = [parseFloat(data[0].lat), parseFloat(data[0].lon)];
                            placeMarker(location);
                            document.getElementById('location-text').textContent = data[0].display_name;
                        } else {
                            alert('Location not found. Please try a different search term.');
                        }
                    })
                    .catch(error => {
                        alert('Error searching for location. Please try again.');
                    });
            }
            
            function useCurrentLocation() {
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(
                        function(position) {
                            const location = [position.coords.latitude, position.coords.longitude];
                            placeMarker(location);
                            document.getElementById('location-text').textContent = 'Your current location';
                        },
                        function() {
                            alert('Unable to get your location. Please select manually.');
                        }
                    );
                } else {
                    alert('Geolocation is not supported by this browser.');
                }
            }
            
            function updateRadius() {
                const slider = document.getElementById('radius-slider');
                currentRadius = parseInt(slider.value);
                document.getElementById('radius-value').textContent = currentRadius;
                document.getElementById('radius-text').textContent = `${currentRadius} km`;
                if (selectedLocation) {
                    placeMarker(selectedLocation);
                }
            }
            
            function updateValue(category) {
                const slider = document.getElementById(category);
                const display = document.getElementById(category + '-value');
                display.textContent = slider.value + '%';
            }
            
            // Initialize map when page loads
            window.onload = function() {
                initMap();
            };
            
            async function getRecommendations() {
                const loading = document.getElementById('loading');
                const results = document.getElementById('results');
                const recommendations = document.getElementById('recommendations');
                
                loading.style.display = 'block';
                results.style.display = 'none';
                
                const preferences = {
                    recreation: parseInt(document.getElementById('recreation').value) / 100,
                    community: parseInt(document.getElementById('community').value) / 100,
                    transport: parseInt(document.getElementById('transport').value) / 100,
                    education: parseInt(document.getElementById('education').value) / 100,
                    utility: parseInt(document.getElementById('utility').value) / 100,
                    latitude: selectedLocation ? selectedLocation.lat : null,
                    longitude: selectedLocation ? selectedLocation.lng : null,
                    radius_km: currentRadius
                };
                
                try {
                    const response = await fetch('/api/recommendations', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(preferences)
                    });
                    
                    const data = await response.json();
                    
                    loading.style.display = 'none';
                    results.style.display = 'block';
                    
                    let html = '';
                    data.forEach((suburb, index) => {
                        const distanceInfo = suburb.distance_km ? `<div style="color: #7f8c8d; font-size: 14px; margin-bottom: 10px;">📍 ${suburb.distance_km.toFixed(1)} km away</div>` : '';
                        html += `
                            <div class="suburb-card">
                                <div class="suburb-name">${index + 1}. ${suburb.suburb_name}</div>
                                ${distanceInfo}
                                <div class="suburb-score">Score: ${(suburb.score * 100).toFixed(1)}%</div>
                                <div class="poi-breakdown">
                                    <div class="poi-category">
                                        <strong>🎾 Recreation</strong><br>${suburb.poi_counts.recreation || 0}
                                    </div>
                                    <div class="poi-category">
                                        <strong>🏘️ Community</strong><br>${suburb.poi_counts.community || 0}
                                    </div>
                                    <div class="poi-category">
                                        <strong>🚌 Transport</strong><br>${suburb.poi_counts.transport || 0}
                                    </div>
                                    <div class="poi-category">
                                        <strong>🎓 Education</strong><br>${suburb.poi_counts.education || 0}
                                    </div>
                                    <div class="poi-category">
                                        <strong>⚡ Utility</strong><br>${suburb.poi_counts.utility || 0}
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                    
                    recommendations.innerHTML = html;
                    
                } catch (error) {
                    loading.style.display = 'none';
                    alert('Error getting recommendations: ' + error.message);
                }
            }
            
            function clearLocation() {
                if (marker) {
                    map.removeLayer(marker);
                }
                if (circle) {
                    map.removeLayer(circle);
                }
                selectedLocation = null;
                document.getElementById('selected-location').style.display = 'none';
                document.getElementById('radius-selector').style.display = 'none';
                document.getElementById('location-search').value = '';
            }
        </script>
        
        <!-- Leaflet CSS and JS (OpenStreetMap) -->
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/api/recommendations", response_model=List[SuburbRecommendation])
async def get_recommendations(preferences: PreferenceWeights):
    """Get suburb recommendations based on user preferences"""
    
    try:
        # Build query based on location filter
        if preferences.latitude and preferences.longitude:
            # Location-based filtering with 5km radius
            radius_km = preferences.radius_km or 5.0
            query = f"""
                SELECT 
                    sa4_name,
                    COUNT(*) as total_pois,
                    COUNT(CASE WHEN group_name = 'Recreation' THEN 1 END) as recreation_count,
                    COUNT(CASE WHEN group_name = 'Community' THEN 1 END) as community_count,
                    COUNT(CASE WHEN group_name = 'Transport' THEN 1 END) as transport_count,
                    COUNT(CASE WHEN group_name = 'Education' THEN 1 END) as education_count,
                    COUNT(CASE WHEN group_name = 'Utility' THEN 1 END) as utility_count,
                    AVG(latitude) as avg_lat,
                    AVG(longitude) as avg_lon,
                    MIN(ST_Distance(
                        geom::geography, 
                        ST_SetSRID(ST_MakePoint({preferences.longitude}, {preferences.latitude}), 4326)::geography
                    ) / 1000) as distance_km
                FROM poi_data 
                WHERE sa4_name IS NOT NULL
                AND ST_DWithin(
                    geom::geography, 
                    ST_SetSRID(ST_MakePoint({preferences.longitude}, {preferences.latitude}), 4326)::geography, 
                    {radius_km * 1000}
                )
                GROUP BY sa4_name
                HAVING COUNT(*) >= 10
                ORDER BY distance_km ASC, total_pois DESC
            """
        else:
            # Original query without location filter
            query = """
                SELECT 
                    sa4_name,
                    COUNT(*) as total_pois,
                    COUNT(CASE WHEN group_name = 'Recreation' THEN 1 END) as recreation_count,
                    COUNT(CASE WHEN group_name = 'Community' THEN 1 END) as community_count,
                    COUNT(CASE WHEN group_name = 'Transport' THEN 1 END) as transport_count,
                    COUNT(CASE WHEN group_name = 'Education' THEN 1 END) as education_count,
                    COUNT(CASE WHEN group_name = 'Utility' THEN 1 END) as utility_count,
                    AVG(latitude) as avg_lat,
                    AVG(longitude) as avg_lon,
                    NULL as distance_km
                FROM poi_data 
                WHERE sa4_name IS NOT NULL
                GROUP BY sa4_name
                HAVING COUNT(*) >= 20
                ORDER BY total_pois DESC
            """
        
        df = pd.read_sql(query, engine)
        
        if df.empty:
            raise HTTPException(status_code=404, detail="No suburb data found")
        
        # Calculate scores based on preferences
        recommendations = []
        for _, row in df.iterrows():
            # Normalize counts to 0-1 scale
            max_pois = df['total_pois'].max()
            normalized_recreation = row['recreation_count'] / max_pois if max_pois > 0 else 0
            normalized_community = row['community_count'] / max_pois if max_pois > 0 else 0
            normalized_transport = row['transport_count'] / max_pois if max_pois > 0 else 0
            normalized_education = row['education_count'] / max_pois if max_pois > 0 else 0
            normalized_utility = row['utility_count'] / max_pois if max_pois > 0 else 0
            
            # Calculate weighted score
            score = (
                preferences.recreation * normalized_recreation +
                preferences.community * normalized_community +
                preferences.transport * normalized_transport +
                preferences.education * normalized_education +
                preferences.utility * normalized_utility
            )
            
            recommendations.append(SuburbRecommendation(
                suburb_name=row['sa4_name'],
                score=score,
                poi_counts={
                    'recreation': int(row['recreation_count']),
                    'community': int(row['community_count']),
                    'transport': int(row['transport_count']),
                    'education': int(row['education_count']),
                    'utility': int(row['utility_count'])
                },
                total_pois=int(row['total_pois']),
                latitude=float(row['avg_lat']) if pd.notna(row['avg_lat']) else None,
                longitude=float(row['avg_lon']) if pd.notna(row['avg_lon']) else None,
                distance_km=float(row['distance_km']) if pd.notna(row['distance_km']) else None
            ))
        
        # Sort by score and return top 10
        recommendations.sort(key=lambda x: x.score, reverse=True)
        return recommendations[:10]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting recommendations: {str(e)}")

@app.get("/api/stats")
async def get_stats():
    """Get overall statistics about the POI data"""
    try:
        query = """
            SELECT 
                COUNT(*) as total_pois,
                COUNT(DISTINCT group_name) as categories,
                group_name,
                COUNT(*) as count
            FROM poi_data 
            GROUP BY group_name
            ORDER BY count DESC
        """
        
        df = pd.read_sql(query, engine)
        
        return {
            "total_pois": int(df['total_pois'].iloc[0]) if not df.empty else 0,
            "categories": int(df['categories'].iloc[0]) if not df.empty else 0,
            "breakdown": df[['group_name', 'count']].to_dict('records')
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
