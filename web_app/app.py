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
import os

# Load configuration
with open('../config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Setup database connection (env var takes precedence)
database_url_env = os.getenv('DATABASE_URL')
if database_url_env and database_url_env.strip():
    db_url = database_url_env
else:
    db_config = config.get('database', {})
    db_url = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['name']}"

engine = create_engine(db_url, echo=False)

app = FastAPI(
    title="Sydney Suburb Recommender",
    description="Find the best suburb in Sydney based on your preferences",
    version="1.0.0"
)

# Add CORS middleware (configurable)
allowed_origins_env = os.getenv('ALLOWED_ORIGINS', '')
allowed_origins = [o.strip() for o in allowed_origins_env.split(',') if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
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
            function updateValue(category) {
                const slider = document.getElementById(category);
                const display = document.getElementById(category + '-value');
                display.textContent = slider.value + '%';
            }
            
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
                    utility: parseInt(document.getElementById('utility').value) / 100
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
                        html += `
                            <div class="suburb-card">
                                <div class="suburb-name">${index + 1}. ${suburb.suburb_name}</div>
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
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/api/recommendations", response_model=List[SuburbRecommendation])
async def get_recommendations(preferences: PreferenceWeights):
    """Get suburb recommendations based on user preferences"""
    
    try:
        # Choose query based on whether location filter is provided
        if preferences.latitude is not None and preferences.longitude is not None:
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
                distance_km=float(row['distance_km']) if 'distance_km' in df.columns and pd.notna(row['distance_km']) else None
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
