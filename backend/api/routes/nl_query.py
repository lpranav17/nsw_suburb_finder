"""Natural Language Query endpoint."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict
import os
import json

router = APIRouter()

class NLQueryRequest(BaseModel):
    """Natural language query request."""
    query: str

class NLQueryResponse(BaseModel):
    """Natural language query response with weights."""
    recreation: float
    community: float
    transport: float
    education: float
    utility: float

def process_with_openai(query: str) -> Dict[str, float]:
    """Process query using OpenAI."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        prompt = f"""Convert this user query into preference weights for suburb recommendations.
Categories: recreation (parks, beaches, sports), community (libraries, centers), transport (public transport), education (schools), utility (services)

User query: "{query}"

Return ONLY valid JSON with weights (0-1) that sum to 1.0:
{{
  "recreation": 0.0-1.0,
  "community": 0.0-1.0,
  "transport": 0.0-1.0,
  "education": 0.0-1.0,
  "utility": 0.0-1.0
}}

Examples:
- "beaches and schools" → {{"recreation": 0.4, "community": 0.1, "transport": 0.2, "education": 0.3, "utility": 0.0}}
- "parks and transport" → {{"recreation": 0.5, "community": 0.1, "transport": 0.4, "education": 0.0, "utility": 0.0}}
"""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200
        )
        
        content = response.choices[0].message.content.strip()
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        
        weights = json.loads(content)
        
        # Validate and normalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        else:
            # Default equal weights
            weights = {k: 0.2 for k in weights.keys()}
        
        return weights
        
    except ImportError:
        raise HTTPException(
            status_code=500, 
            detail="OpenAI package not installed. Add 'openai' to requirements.txt"
        )
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse AI response: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )

@router.post("/api/nl-query", response_model=NLQueryResponse)
async def process_nl_query(request: NLQueryRequest):
    """
    Convert natural language query to preference weights.
    
    Example queries:
    - "Find suburbs near beaches with good schools"
    - "I want areas with lots of parks and public transport"
    - "Show me suburbs with excellent education facilities"
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # Check if OpenAI is configured
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="OpenAI API key not configured. Please set OPENAI_API_KEY environment variable."
        )
    
    try:
        weights = process_with_openai(request.query.strip())
        return NLQueryResponse(**weights)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )

