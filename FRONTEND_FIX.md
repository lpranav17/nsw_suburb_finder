# Fix Frontend-Backend Connection

## Problem
Frontend can't connect to backend API

## Quick Fix Steps

### 1. Check Environment Variable in Vercel

1. **Go to Vercel Dashboard:**
   - https://vercel.com
   - Select your project

2. **Settings → Environment Variables:**
   - Find `NEXT_PUBLIC_API_URL`
   - Should be: `https://nsw-suburb-finder-backend-production.up.railway.app`
   - If missing or wrong, update it

3. **Redeploy:**
   - Go to Deployments
   - Click "Redeploy" on latest deployment

### 2. Update CORS in Railway

1. **Go to Railway Dashboard:**
   - Select your backend service
   - Go to Variables tab

2. **Set `ALLOWED_ORIGINS`:**
   ```
   ALLOWED_ORIGINS=https://your-frontend.vercel.app,http://localhost:3000
   ```
   - Replace `your-frontend.vercel.app` with your actual Vercel URL
   - Include `http://localhost:3000` for local development

3. **Railway will auto-redeploy**

### 3. Test the Connection

**In Browser Console (F12):**
```javascript
// Test if env var is set
console.log('API URL:', process.env.NEXT_PUBLIC_API_URL);

// Test API directly
fetch('https://nsw-suburb-finder-backend-production.up.railway.app/api/stats')
  .then(r => r.json())
  .then(console.log)
  .catch(console.error);
```

### 4. Common Issues

**Issue: "Set NEXT_PUBLIC_API_URL in your environment"**
- **Fix:** Set the env var in Vercel (see step 1)

**Issue: CORS error in console**
- **Fix:** Update `ALLOWED_ORIGINS` in Railway (see step 2)

**Issue: 404 Not Found**
- **Fix:** Check the Railway URL is correct
- Test: `https://nsw-suburb-finder-backend-production.up.railway.app/health`

**Issue: 500 Error**
- **Fix:** Check Railway logs for database connection issues

## Your Current URLs

- **Backend:** `https://nsw-suburb-finder-backend-production.up.railway.app`
- **Frontend:** (Check your Vercel dashboard)

## Quick Test Commands

```powershell
# Test backend health
Invoke-RestMethod -Uri "https://nsw-suburb-finder-backend-production.up.railway.app/health"

# Test backend API
$body = '{"recreation":0.25,"community":0.25,"transport":0.25,"education":0.15,"utility":0.1}'
Invoke-RestMethod -Uri "https://nsw-suburb-finder-backend-production.up.railway.app/api/recommendations" -Method POST -ContentType "application/json" -Body $body
```

