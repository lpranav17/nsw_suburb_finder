# Fixing Railway Healthcheck Failure

## Problem
Your deployment is failing at the **Healthcheck** stage. This means:
- ✅ Build succeeded
- ✅ Deploy succeeded  
- ❌ Healthcheck failed (app not responding)

## What I Fixed

1. **Added `/health` endpoint** - Simple endpoint that doesn't require database
2. **Made config loading safe** - Won't crash if config.yaml is missing
3. **Updated railway.json** - Added healthcheck path configuration

## Next Steps

1. **Commit and push the fixes:**
   ```bash
   git add backend/api/app.py backend/railway.json
   git commit -m "Fix healthcheck endpoint and config loading"
   git push origin main
   ```

2. **Check Railway logs:**
   - Go to Railway → Deployments → Click on the failed deployment
   - Click "View logs"
   - Look for errors in the "Deploy" section
   - Common issues:
     - Database connection errors
     - Missing environment variables
     - Import errors

3. **Verify environment variables:**
   - Go to Railway → Variables tab
   - Make sure `DATABASE_URL` is set correctly
   - The app should still start even if database connection fails (it will just error on API calls)

4. **Redeploy:**
   - Railway should auto-deploy after you push
   - Or manually trigger: Deployments → Redeploy

## What to Check in Logs

Look for these errors:

### Database Connection Error
```
sqlalchemy.exc.OperationalError: could not connect to server
```
**Fix**: Check `DATABASE_URL` environment variable

### Import Error
```
ModuleNotFoundError: No module named 'xxx'
```
**Fix**: Check `requirements.txt` has all dependencies

### Config File Error
```
FileNotFoundError: config/config.yaml
```
**Fix**: Already fixed - config loading is now safe

### Port Error
```
Address already in use
```
**Fix**: Make sure using `$PORT` environment variable

## Test Healthcheck Locally

Before pushing, test locally:
```bash
cd backend/api
python app.py
# In another terminal:
curl http://localhost:8000/health
# Should return: {"status":"ok","service":"nsw-suburb-finder-backend"}
```
