#!/usr/bin/env python3
"""
Start the Sydney Suburb Recommender web application
"""

import uvicorn
from app import app

if __name__ == "__main__":
    print("🚀 Starting Sydney Suburb Recommender...")
    print("📱 Open your browser and go to: http://localhost:8000")
    print("🔧 API documentation: http://localhost:8000/docs")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
