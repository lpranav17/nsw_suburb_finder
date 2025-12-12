# Deployment Guide - Railway & Neon

## Step 1: Setup Neon Database (PostgreSQL with PostGIS)

### 1.1 Create Neon Account
1. Go to [neon.tech](https://neon.tech)
2. Sign up for free account
3. Create a new project

### 1.2 Create Database
1. In Neon dashboard, create a new database
2. Note the connection string (looks like: `postgresql://user:password@host/dbname`)
3. Enable PostGIS extension:
   - Go to SQL Editor in Neon dashboard
   - Run: `CREATE EXTENSION IF NOT EXISTS postgis;`

### 1.3 Get Connection String
 - Copy the connection string from Neon dashboard
- Format: `postgresql://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require`
- Save this for Railway setup

---

## Step 2: Setup Railway Backend

### 2.1 Create Railway Account
1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub (free tier available)
3. Connect your GitHub repository

### 2.2 Deploy Backend
1. Click "New Project" → "Deploy from GitHub repo"
2. Select your `nsw_suburb_finder` repository
3. Railway will auto-detect it's a Python project
4. Set root directory: `backend`
5. Railway will use `railway.json` config

### 2.3 Configure Environment Variables
In Railway dashboard, add these environment variables:

```
DATABASE_URL=postgresql://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
ALLOWED_ORIGINS=https://your-frontend.vercel.app,http://localhost:3000
PORT=8000
```

**Important**: 
- Replace `DATABASE_URL` with your Neon connection string
- Replace `ALLOWED_ORIGINS` with your Vercel frontend URL

### 2.4 Deploy
1. Railway will automatically deploy
2. Wait for build to complete
3. Get your backend URL (e.g., `https://your-app.railway.app`)

---

## Step 3: Setup Vercel Frontend

### 3.1 Deploy Frontend
1. Go to [vercel.com](https://vercel.com)
2. Import your GitHub repository
3. Set root directory: `frontend`
4. Framework preset: Next.js

### 3.2 Configure Environment Variables
In Vercel dashboard, add:

```
NEXT_PUBLIC_API_URL=https://your-app.railway.app
```

Replace with your Railway backend URL

### 3.3 Deploy
1. Click Deploy
2. Vercel will build and deploy automatically
3. Get your frontend URL (e.g., `https://your-app.vercel.app`)

---

## Step 4: Populate Database

### 4.1 Run Data Collection Script
You have two options:

#### Option A: Run Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variable
export DATABASE_URL="your-neon-connection-string"

# Run collection script
cd backend/scripts
python collect_data.py
```

#### Option B: Run on Railway (One-time)
1. In Railway dashboard, go to your service
2. Click "Deployments" → "New Deployment"
3. Or use Railway CLI:
```bash
railway run python backend/scripts/collect_data.py
```

### 4.2 Verify Data
Check your database in Neon dashboard:
- Should see `poi_data` table
- Should have ~8,000+ POI records

---

## Step 5: Update CORS Settings

After deploying frontend, update Railway environment variable:

```
ALLOWED_ORIGINS=https://your-frontend.vercel.app
```

Then redeploy backend.

---

## Step 6: Test Everything

1. **Frontend**: Visit your Vercel URL
2. **Backend API**: Visit `https://your-backend.railway.app/api/stats`
3. **API Docs**: Visit `https://your-backend.railway.app/docs`

---

## Troubleshooting

### Database Connection Issues
- Check `DATABASE_URL` format
- Ensure PostGIS extension is enabled
- Check Neon database is running

### CORS Errors
- Verify `ALLOWED_ORIGINS` includes your frontend URL
- Check for trailing slashes
- Ensure backend is deployed and running

### Build Failures
- Check Railway logs
- Verify `requirements.txt` is in `backend/` directory
- Ensure Python version is compatible

---

## Cost Estimate

- **Neon**: Free tier (0.5 GB storage, unlimited projects)
- **Railway**: Free tier ($5 credit/month, ~500 hours)
- **Vercel**: Free tier (unlimited deployments)

**Total**: $0/month for small projects! 🎉

---

## Next Steps

1. Set up scheduled data refresh (GitHub Actions)
2. Add OpenAI/HuggingFace API for NL queries
3. Monitor usage and scale if needed
