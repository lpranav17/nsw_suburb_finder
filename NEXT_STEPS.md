# Next Steps Guide

## ✅ Completed
- ✅ Project restructured (backend/frontend separation)
- ✅ Backend deployed to Railway
- ✅ Database setup on Neon
- ✅ Repository cleaned up

---

## Step 1: Populate Database with POI Data

### Option A: Run Locally (Recommended for first time)

1. **Install dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Set environment variable:**
   ```bash
   # Windows PowerShell
   $env:DATABASE_URL="postgresql://neondb_owner:npg_GkymW1Y8Ersc@ep-autumn-art-a72z129d-pooler.ap-southeast-2.aws.neon.tech/database?sslmode=require&channel_binding=require"
   
   # Or create .env file in backend/ directory:
   # DATABASE_URL=postgresql://neondb_owner:npg_GkymW1Y8Ersc@ep-autumn-art-a72z129d-pooler.ap-southeast-2.aws.neon.tech/database?sslmode=require&channel_binding=require
   ```

3. **Run data collection script:**
   ```bash
   cd backend/scripts
   python collect_data.py
   ```

4. **Verify data:**
   - Go to Neon dashboard → SQL Editor
   - Run: `SELECT COUNT(*) FROM poi_data;`
   - Should show ~8,000+ POIs

### Option B: Run on Railway (Alternative)

1. **Install Railway CLI:**
   ```bash
   # Windows
   iwr https://railway.app/install.ps1 -useb | iex
   ```

2. **Login to Railway:**
   ```bash
   railway login
   ```

3. **Link to your project:**
   ```bash
   railway link
   # Select your nsw-suburb-finder-backend project
   ```

4. **Run the script:**
   ```bash
   cd backend/scripts
   railway run python collect_data.py
   ```

**Note**: This will use the `DATABASE_URL` environment variable already set in Railway.

---

## Step 2: Deploy Frontend to Vercel

### 2.1 Setup Vercel

1. **Go to [vercel.com](https://vercel.com)**
2. **Sign up/Login** with GitHub
3. **Click "Add New Project"**
4. **Import your repository:**
   - Select `nsw_suburb_finder`
   - Click "Import"

### 2.2 Configure Project

1. **Project Settings:**
   - **Framework Preset**: Next.js
   - **Root Directory**: `frontend` (IMPORTANT!)
   - **Build Command**: `npm run build` (auto-detected)
   - **Output Directory**: `.next` (auto-detected)

2. **Environment Variables:**
   - Click "Environment Variables"
   - Add:
     ```
     Name: NEXT_PUBLIC_API_URL
     Value: https://your-backend.railway.app
     ```
   - Replace with your actual Railway backend URL
   - Make sure it's available for "Production", "Preview", and "Development"

3. **Deploy:**
   - Click "Deploy"
   - Wait for build to complete
   - Get your frontend URL (e.g., `https://nsw-suburb-finder.vercel.app`)

### 2.3 Update CORS in Railway

1. **Go back to Railway:**
   - Variables tab
   - Update `ALLOWED_ORIGINS`:
     ```
     ALLOWED_ORIGINS=https://your-frontend.vercel.app,http://localhost:3000
     ```
   - Replace with your actual Vercel URL

2. **Redeploy backend:**
   - Railway will auto-redeploy
   - Or manually: Deployments → Redeploy

### 2.4 Test Everything

1. **Frontend**: Visit your Vercel URL
2. **Backend API**: `https://your-backend.railway.app/api/stats`
3. **API Docs**: `https://your-backend.railway.app/docs`
4. **Test recommendations**: Use the frontend to get suburb recommendations

---

## Step 3: Add Natural Language Query Support

### 3.1 Choose AI Provider

**Option A: OpenAI (Recommended)**
- More accurate
- Better at understanding context
- ~$0.01-0.03 per query

**Option B: HuggingFace (Free)**
- Free tier available
- Good for simple queries
- May be slower

### 3.2 Setup OpenAI (Recommended)

1. **Get API Key:**
   - Go to [platform.openai.com](https://platform.openai.com)
   - Sign up/Login
   - Go to API Keys
   - Create new secret key
   - Copy the key

2. **Add to Railway:**
   - Railway → Variables tab
   - Add:
     ```
     Name: OPENAI_API_KEY
     Value: sk-...your-key...
     ```

3. **Install OpenAI package:**
   - Add to `backend/requirements.txt`:
     ```
     openai==1.3.0
     ```

4. **Create NL Query Endpoint:**
   - Create `backend/api/routes/nl_query.py`:
   ```python
   from fastapi import APIRouter, HTTPException
   from pydantic import BaseModel
   from openai import OpenAI
   import os
   
   router = APIRouter()
   client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
   
   class NLQueryRequest(BaseModel):
       query: str
   
   @router.post("/api/nl-query")
   async def process_nl_query(request: NLQueryRequest):
       """Convert natural language to preference weights"""
       
       prompt = f"""
       Convert this user query into preference weights for suburb recommendations.
       Categories: recreation, community, transport, education, utility
       
       User query: "{request.query}"
       
       Return JSON with weights (0-1) that sum to 1.0:
       {{
         "recreation": 0.0-1.0,
         "community": 0.0-1.0,
         "transport": 0.0-1.0,
         "education": 0.0-1.0,
         "utility": 0.0-1.0
       }}
       
       Example: "I want suburbs near beaches with good schools"
       Response: {{"recreation": 0.4, "community": 0.1, "transport": 0.2, "education": 0.3, "utility": 0.0}}
       """
       
       try:
           response = client.chat.completions.create(
               model="gpt-3.5-turbo",
               messages=[{"role": "user", "content": prompt}],
               temperature=0.3,
               max_tokens=150
           )
           
           import json
           weights = json.loads(response.choices[0].message.content)
           
           return weights
           
       except Exception as e:
           raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")
   ```

5. **Update app.py:**
   ```python
   from api.routes.nl_query import router as nl_query_router
   
   app.include_router(nl_query_router)
   ```

6. **Update frontend:**
   - Add NL query input field
   - Call `/api/nl-query` endpoint
   - Use returned weights for recommendations

### 3.3 Setup HuggingFace (Alternative)

1. **Get API Key:**
   - Go to [huggingface.co](https://huggingface.co)
   - Sign up/Login
   - Go to Settings → Access Tokens
   - Create new token

2. **Add to Railway:**
   ```
   Name: HUGGINGFACE_API_KEY
   Value: hf_...your-token...
   ```

3. **Install package:**
   ```
   transformers==4.35.0
   ```

4. **Similar implementation** but using HuggingFace models

---

## Step 4: Test Natural Language Queries

### Test Queries:
- "Find suburbs near beaches with good schools"
- "I want areas with lots of parks and public transport"
- "Show me suburbs with excellent education facilities"
- "Areas with good community centers and utilities"

### Expected Flow:
1. User types query in frontend
2. Frontend calls `/api/nl-query` with query
3. AI converts to preference weights
4. Frontend calls `/api/recommendations` with weights
5. Display results

---

## Step 5: Optional Enhancements

### 5.1 Add Caching
- Cache NL query results (same query = same weights)
- Use Redis or in-memory cache
- Reduces API costs

### 5.2 Add Rate Limiting
- Limit NL queries per user/IP
- Protect against abuse
- Use FastAPI rate limiting middleware

### 5.3 Add Query History
- Store user queries
- Show recent searches
- Learn from patterns

### 5.4 Scheduled Data Refresh
- Set up GitHub Actions
- Run data collection monthly
- Keep POI data fresh

---

## Quick Checklist

- [ ] Database populated with POI data
- [ ] Frontend deployed to Vercel
- [ ] CORS configured correctly
- [ ] Frontend and backend communicating
- [ ] OpenAI/HuggingFace API key added
- [ ] NL query endpoint created
- [ ] Frontend updated to use NL queries
- [ ] Tested end-to-end

---

## Need Help?

If you get stuck:
1. Check Railway logs for backend errors
2. Check Vercel build logs for frontend errors
3. Test API endpoints directly (use `/docs` on Railway)
4. Verify environment variables are set correctly
