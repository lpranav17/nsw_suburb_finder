# Fix Vercel Environment Variable Error

## Problem
Error: "A variable with the name `NEXT_PUBLIC_API_URL` already exists"

## Solution: Edit Existing Variable

### Step-by-Step:

1. **Go to Vercel Dashboard:**
   - https://vercel.com
   - Login to your account

2. **Navigate to Your Project:**
   - Click on your project name (`nsw_suburb_finder` or similar)
   - Go to **Settings** tab (top navigation)

3. **Find Environment Variables:**
   - In Settings, click **"Environment Variables"** in the left sidebar
   - You should see a list of all environment variables

4. **Locate `NEXT_PUBLIC_API_URL`:**
   - Scroll through the list
   - Find `NEXT_PUBLIC_API_URL`
   - It might show `http://localhost:8000` as the current value

5. **Edit the Variable:**
   - Click on the variable name or the **pencil/edit icon** (usually on the right)
   - **OR** click the three dots (...) menu → "Edit"
   - Update the value to your Railway backend URL:
     ```
     https://your-backend.railway.app
     ```
   - Replace `your-backend.railway.app` with your actual Railway URL
   - Make sure it's enabled for: Production, Preview, Development
   - Click **"Save"**

6. **Redeploy:**
   - Go to **Deployments** tab
   - Click the three dots on the latest deployment
   - Click **"Redeploy"**
   - Or push a new commit to trigger auto-deploy

## If You Can't Find It

### Check Different Scopes:
- Look for tabs/filters: "Production", "Preview", "Development"
- The variable might be set for a specific environment
- Check all three

### Alternative: Delete and Recreate
1. Find the variable
2. Click delete/trash icon
3. Confirm deletion
4. Click **"Add New"**
5. Name: `NEXT_PUBLIC_API_URL`
6. Value: `https://your-backend.railway.app`
7. Select all environments (Production, Preview, Development)
8. Save

## Get Your Railway Backend URL

1. Go to Railway dashboard
2. Click on your project: `nsw-suburb-finder-backend`
3. Go to **Settings** tab
4. Scroll to **"Domains"** or **"Networking"** section
5. Copy the URL (looks like: `https://nsw-suburb-finder-backend-production.up.railway.app`)

## Verify It's Working

After updating:
1. Redeploy Vercel project
2. Visit your Vercel URL
3. Open browser console (F12)
4. Check Network tab - API calls should go to Railway URL, not localhost

