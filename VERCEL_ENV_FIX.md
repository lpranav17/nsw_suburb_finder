# Fix Vercel Environment Variable

## Problem
The frontend is trying to call: `/nsw-suburb-finder-backend.railway.internal/api/recommendations`
This is wrong - it's using a relative path with an internal Railway domain.

## Solution

### Update `NEXT_PUBLIC_API_URL` in Vercel

1. **Go to Vercel Dashboard:**
   - https://vercel.com
   - Select your project: `nsw-suburb-finder-7s9mlmw31-lpranav17s-projects`

2. **Settings → Environment Variables:**
   - Find `NEXT_PUBLIC_API_URL`
   - **Current (WRONG):** Probably `nsw-suburb-finder-backend.railway.internal` or similar
   - **Change to (CORRECT):** 
     ```
     https://nsw-suburb-finder-backend-production.up.railway.app
     ```
   - **IMPORTANT:** Must include `https://` at the start!
   - **IMPORTANT:** No trailing slash at the end!

3. **Make sure it's enabled for:**
   - ✅ Production
   - ✅ Preview  
   - ✅ Development

4. **Save the variable**

5. **Redeploy:**
   - Go to Deployments tab
   - Click "..." on latest deployment
   - Click "Redeploy"
   - OR push a new commit to trigger auto-deploy

## Verify

After redeploy, the request should go to:
```
https://nsw-suburb-finder-backend-production.up.railway.app/api/recommendations
```

NOT:
```
https://nsw-suburb-finder-7s9mlmw31-lpranav17s-projects.vercel.app/nsw-suburb-finder-backend.railway.internal/api/recommendations
```

## Quick Check

In browser console after redeploy:
```javascript
console.log('API URL:', process.env.NEXT_PUBLIC_API_URL);
// Should show: https://nsw-suburb-finder-backend-production.up.railway.app
```

