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

# Ensure transformers does not try to import TensorFlow / Flax,
# which are not needed for sentence-transformers in this app.
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")

import numpy as np

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    _HAS_SENTENCE_TRANSFORMERS = True
except Exception:  # ModuleNotFoundError or any other import issue
    SentenceTransformer = None  # type: ignore
    _HAS_SENTENCE_TRANSFORMERS = False

# Load configuration
from pathlib import Path
config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
config = {}
if config_path.exists():
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f) or {}

# Setup database connection (env var takes precedence)
database_url_env = os.getenv('DATABASE_URL')
if database_url_env and database_url_env.strip():
    db_url = database_url_env
else:
    db_config = config.get('database', {})
    db_url = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['name']}"

try:
    engine = create_engine(db_url, echo=False)
    # Test connection
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
except Exception as e:
    print(f"WARNING: Database connection failed: {e}")
    print("App will start but database endpoints may not work")
    engine = None

# ---------- Natural language → preference weights (embedding + keyword fallback) ----------

# Default weights if we can't infer anything better
DEFAULT_WEIGHTS: Dict[str, float] = {
    "recreation": 0.25,
    "community": 0.25,
    "transport": 0.25,
    "education": 0.15,
    "utility": 0.10,
}

# Example natural language profiles with hand-tuned weights (for embedding-based mode).
# These should sum to ~1.0 across the five dimensions.
EXAMPLE_QUERIES = [
    {
        "text": "great for families with young kids, safe and quiet with good schools",
        "weights": {
            "recreation": 0.20,
            "community": 0.30,
            "transport": 0.15,
            "education": 0.30,
            "utility": 0.05,
        },
    },
    {
        "text": "lots of nightlife, bars and restaurants, great public transport, close to the city",
        "weights": {
            "recreation": 0.35,
            "community": 0.15,
            "transport": 0.30,
            "education": 0.10,
            "utility": 0.10,
        },
    },
    {
        "text": "budget friendly suburb with basic amenities, okay transport, nothing too fancy",
        "weights": {
            "recreation": 0.15,
            "community": 0.20,
            "transport": 0.25,
            "education": 0.15,
            "utility": 0.25,
        },
    },
    {
        "text": "quiet area for retirees, close to healthcare and essential services, peaceful community",
        "weights": {
            "recreation": 0.15,
            "community": 0.30,
            "transport": 0.15,
            "education": 0.05,
            "utility": 0.35,
        },
    },
    {
        "text": "good for students, close to universities and TAFEs, strong public transport",
        "weights": {
            "recreation": 0.20,
            "community": 0.20,
            "transport": 0.30,
            "education": 0.25,
            "utility": 0.05,
        },
    },
    {
        "text": "balanced lifestyle with parks, decent schools, community feel and good transport options",
        "weights": {
            "recreation": 0.25,
            "community": 0.25,
            "transport": 0.25,
            "education": 0.20,
            "utility": 0.05,
        },
    },
]

_embedding_model: Optional[object] = None
_example_embeddings: Optional[np.ndarray] = None


def _get_embedding_state() -> tuple[object, np.ndarray]:
    """
    Lazily load the sentence-transformers model and example embeddings.
    This keeps startup time reasonable and ensures we only load once.
    """
    global _embedding_model, _example_embeddings

    if not _HAS_SENTENCE_TRANSFORMERS:
        raise RuntimeError("sentence-transformers library is not available")

    if _embedding_model is None:
        # Small, fast model that runs locally on CPU (when available).
        _embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")  # type: ignore
        texts = [ex["text"] for ex in EXAMPLE_QUERIES]
        _example_embeddings = _embedding_model.encode(texts, normalize_embeddings=True)  # type: ignore

    # mypy/runtime safety: _example_embeddings will be set with model
    assert _example_embeddings is not None
    return _embedding_model, _example_embeddings


FALLBACK_KEYWORDS: Dict[str, List[str]] = {
    "recreation": [
        "park",
        "parks",
        "beach",
        "beaches",
        "sports",
        "gym",
        "pool",
        "playground",
        "green space",
        "nature",
        "outdoors",
        "recreation",
        "nightlife",
        "bars",
        "restaurants",
    ],
    "community": [
        "community",
        "family",
        "family-friendly",
        "families",
        "kids",
        "safe",
        "quiet",
        "peaceful",
        "neighbourly",
        "neighborhood",
        "village",
        "local vibe",
        "community centre",
        "community center",
        "library",
    ],
    "transport": [
        "transport",
        "public transport",
        "train",
        "station",
        "bus",
        "metro",
        "light rail",
        "tram",
        "easy commute",
        "close to city",
        "near cbd",
        "good transport",
        "strong transport",
    ],
    "education": [
        "school",
        "schools",
        "good schools",
        "education",
        "university",
        "uni",
        "college",
        "tafes",
        "students",
        "student",
        "children's education",
    ],
    "utility": [
        "shopping",
        "shops",
        "supermarket",
        "mall",
        "services",
        "hospital",
        "clinic",
        "doctor",
        "healthcare",
        "infrastructure",
        "amenities",
        "essential services",
    ],
}


def _infer_weights_keyword(query: str) -> Dict[str, float]:
    """Fallback rule-based mapper from text to weights using simple keyword counts."""
    text = (query or "").strip().lower()
    if not text:
        return DEFAULT_WEIGHTS.copy()

    scores: Dict[str, float] = {k: 0.0 for k in DEFAULT_WEIGHTS.keys()}
    for category, words in FALLBACK_KEYWORDS.items():
        for w in words:
            if w in text:
                scores[category] += 1.0

    if all(v == 0.0 for v in scores.values()):
        return DEFAULT_WEIGHTS.copy()

    total = sum(scores.values()) or 1.0
    return {k: float(v / total) for k, v in scores.items()}


def infer_weights_from_nl_query(query: str) -> Dict[str, float]:
    """
    Given a natural-language description, prefer the embedding-based
    interpretation when sentence-transformers is available; otherwise,
    fall back to the lightweight keyword-based mapping.
    """
    query = (query or "").strip()
    if not query:
        return DEFAULT_WEIGHTS.copy()

    # If we don't have sentence-transformers (e.g. on Railway), use keyword rules.
    if not _HAS_SENTENCE_TRANSFORMERS:
        return _infer_weights_keyword(query)

    try:
        model, example_embs = _get_embedding_state()

        # Encode query and compute cosine similarity with example embeddings
        q_vec = model.encode(query, normalize_embeddings=True)  # type: ignore
        sims = np.dot(example_embs, q_vec)  # shape (N,)

        # Use top-k most similar examples
        top_k = min(3, len(EXAMPLE_QUERIES))
        idx = np.argsort(-sims)[:top_k]
        top_sims = sims[idx]

        # If everything is very dissimilar, fall back to keyword/default behavior
        if np.all(top_sims <= 0):
            return _infer_weights_keyword(query)

        # Normalize similarities to sum to 1
        weights_norm = top_sims / (top_sims.sum() or 1.0)

        # Blend example weights
        agg = {
            "recreation": 0.0,
            "community": 0.0,
            "transport": 0.0,
            "education": 0.0,
            "utility": 0.0,
        }
        for w, i in zip(weights_norm, idx):
            ex_weights = EXAMPLE_QUERIES[i]["weights"]
            for key in agg.keys():
                agg[key] += w * ex_weights[key]

        # Renormalize to sum to 1 exactly (defensive)
        total = sum(agg.values()) or 1.0
        for key in agg.keys():
            agg[key] = float(agg[key] / total)

        return agg
    except Exception:
        # If anything goes wrong with the embedding path, degrade gracefully.
        return _infer_weights_keyword(query)

app = FastAPI(
    title="Sydney Suburb Recommender",
    description="Find the best suburb in Sydney based on your preferences",
    version="1.0.0"
)

# Add CORS middleware FIRST (before routes) - this handles OPTIONS automatically
allowed_origins_env = os.getenv('ALLOWED_ORIGINS', '')
# Clean up origins: remove trailing slashes and whitespace
allowed_origins = []
if allowed_origins_env:
    for origin in allowed_origins_env.split(','):
        cleaned = origin.strip().rstrip('/')
        if cleaned:
            allowed_origins.append(cleaned)

# If no origins specified, allow all (for development)
if not allowed_origins:
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
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


class NLQueryRequest(BaseModel):
    """Request body for natural-language suburb search."""

    query: str


class NLQueryResponse(BaseModel):
    """Response for natural-language suburb search."""

    interpreted_preferences: PreferenceWeights
    recommendations: List[SuburbRecommendation]

# Health check endpoint for Railway
@app.get("/health")
async def health_check():
    """Health check endpoint for Railway"""
    return {"status": "ok", "service": "nsw-suburb-finder-backend"}

# Natural-language query endpoint (reuses existing recommendation logic)
@app.post("/api/nl_query", response_model=NLQueryResponse)
async def nl_query(payload: NLQueryRequest):
    """
    Turn a natural-language suburb description into PreferenceWeights
    using local embeddings, then reuse the standard recommendation logic.
    """
    try:
        if not payload.query or not payload.query.strip():
            raise HTTPException(status_code=400, detail="Query must not be empty")

        # 1. Infer weights from the free-text query
        raw_weights = infer_weights_from_nl_query(payload.query)
        prefs = PreferenceWeights(**raw_weights)

        # 2. Reuse the core recommendation logic
        recommendations = await get_recommendations(prefs)

        return NLQueryResponse(
            interpreted_preferences=prefs,
            recommendations=recommendations,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing NL query: {str(e)}")

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
        if engine is None:
            raise HTTPException(status_code=503, detail="Database connection not available")
        
        # Choose query based on whether location filter is provided
        # Only use location filter if valid coordinates are provided (not 0,0 and within reasonable bounds)
        use_location = (preferences.latitude is not None and preferences.longitude is not None 
                       and preferences.latitude != 0 and preferences.longitude != 0
                       and -90 <= preferences.latitude <= 90 and -180 <= preferences.longitude <= 180)
        
        if use_location:
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

        if engine is None:
            raise HTTPException(status_code=503, detail="Database connection not available")
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
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = str(e) if str(e) else repr(e)
        traceback_str = traceback.format_exc()
        print(f"Error in get_recommendations: {error_details}")
        print(f"Traceback: {traceback_str}")
        raise HTTPException(status_code=500, detail=f"Error getting recommendations: {error_details}")

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
        
        if engine is None:
            raise HTTPException(status_code=503, detail="Database connection not available")
        df = pd.read_sql(query, engine)
        
        return {
            "total_pois": int(df['total_pois'].iloc[0]) if not df.empty else 0,
            "categories": int(df['categories'].iloc[0]) if not df.empty else 0,
            "breakdown": df[['group_name', 'count']].to_dict('records')
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")

@app.get("/api/routes")
async def list_routes():
    """List all available API routes - for debugging"""
    routes = []
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods)
            })
    return {"routes": routes, "total": len(routes)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
