# Deployment Guide - VEGAH Compliance Intelligence

Complete step-by-step guide for deploying VEGAH to Render or other platforms.

## Table of Contents

1. [Render Deployment](#render-deployment)
2. [Build Instructions](#build-instructions)
3. [Environment Setup](#environment-setup)
4. [Monitoring & Troubleshooting](#monitoring--troubleshooting)

---

## Render Deployment

### Prerequisites

- GitHub repository with project code
- Render account (https://render.com)
- Environment variables ready (API keys, Qdrant credentials)

### Step 1: Configure Backend (FastAPI)

The project includes `render.yaml` at root with both backend and frontend configurations.

**What Render.yaml Contains:**

```yaml
services:
  - backend (FastAPI on port 8000)
  - frontend (Next.js on port 3000)
```

### Step 2: Deploy Backend Service

1. Go to https://render.com/dashboard
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Configure:
   - **Name**: `vegah-backend`
   - **Environment**: `Python 3`
   - **Build Command**:
     ```bash
     cd backend && pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000
     ```
   - **Instance Type**: Standard (0.5 CPU, 512MB RAM) or higher

5. Add Environment Variables:

   ```
   ANTHROPIC_API_KEY=sk-ant-...
   OPENAI_API_KEY=sk-proj-...
   GROQ_API_KEY=gsk_...
   QDRANT_URL=https://...aws.cloud.qdrant.io
   QDRANT_API_KEY=eyJ...
   DEBUG=false
   ```

6. Click **"Create Web Service"**

### Step 3: Deploy Frontend Service

1. Click **"New +"** → **"Web Service"** again
2. Connect the same GitHub repository
3. Configure:
   - **Name**: `vegah-frontend`
   - **Environment**: `Node`
   - **Build Command**:
     ```bash
     cd frontend && npm install && npm run build
     ```
   - **Start Command**:
     ```bash
     cd frontend && npm start
     ```
   - **Instance Type**: Standard (0.5 CPU, 512MB RAM) or higher

4. Add Environment Variables:

   ```
   NEXT_PUBLIC_API_URL=https://vegah-backend.onrender.com
   ```

   (Replace with your actual backend URL)

5. Click **"Create Web Service"**

### Step 4: Connect Services

1. Go to backend service settings
2. Under **"Environment"**, add:
   ```
   FRONTEND_URL=https://vegah-frontend.onrender.com
   ALLOWED_ORIGINS=https://vegah-frontend.onrender.com,https://your-domain.com
   ```

### Step 5: Deploy

1. Render auto-deploys on git push to main branch
2. Or manually trigger deployment:
   - Go to service → **"Manual Deploy"** → **"Deploy latest commit"**

### Step 6: Verify Deployment

1. Backend: Visit `https://vegah-backend.onrender.com/health`

   ```json
   {
     "status": "healthy",
     "qdrant_connected": true
   }
   ```

2. Frontend: Visit `https://vegah-frontend.onrender.com`
   - Should load successfully
   - Upload zone and process buttons visible

---

## Build Instructions

### Local Build Testing

Before deploying, test builds locally:

#### 1. Backend Build

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
# or: source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**Check**: http://localhost:8000/docs should show API documentation

#### 2. Frontend Build

```bash
cd frontend
npm install
npm run build
npm start
```

**Check**: http://localhost:3000 should load without errors

### Production Build Optimization

#### Backend

- FastAPI requires only dependency installation
- No build step needed
- Use `gunicorn` for multiple workers:
  ```bash
  gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
  ```

#### Frontend

- Next.js builds static and server pages
- Build command: `npm run build`
- Output: `.next/` directory
- Start: `npm start` runs production server

### Build Artifacts Size

- Backend: ~500MB with dependencies
- Frontend: ~200MB with dependencies
- Total: ~700MB (should fit within Render's limits)

---

## Environment Setup

### Critical Environment Variables

#### Backend (.env)

```bash
# LLM API Keys
ANTHROPIC_API_KEY=sk-ant-...        # Claude API key
OPENAI_API_KEY=sk-proj-...          # GPT-4 API key
GROQ_API_KEY=gsk_...                # Groq API key

# Vector Database
QDRANT_URL=https://...aws.cloud.qdrant.io
QDRANT_API_KEY=eyJ...

# Application
DEBUG=false                          # Set to false in production
APP_NAME=VEGAH Compliance Intelligence

# Collections
CAPABILITIES_COLLECTION=vegah_capabilities
PROPOSALS_COLLECTION=vegah_proposals
```

#### Frontend (.env.local)

```bash
NEXT_PUBLIC_API_URL=https://vegah-backend.onrender.com
```

### Render Environment Variables UI

1. Service → **"Environment"**
2. Click **"Add Environment Variable"** for each variable
3. For sensitive values (API keys):
   - Use Render's encrypted storage
   - Never commit to git

---

## Monitoring & Troubleshooting

### View Logs

#### Render Dashboard

1. Service → **"Logs"** tab
2. Real-time log streaming
3. Export logs for analysis

#### Common Errors

**Backend Won't Start**

```
ModuleNotFoundError: No module named 'fastapi'
```

Fix: Ensure `cd backend` in build command before `pip install`

**Frontend Build Fails**

```
npm ERR! code EACCES
```

Fix: Clear npm cache: `npm cache clean --force` before build

**API Connection Fails**

```
Backend error: "fetch failed"
```

Fix: Verify `NEXT_PUBLIC_API_URL` matches backend URL in frontend env

**Qdrant Connection Error**

```
qdrant_client.exceptions.UnexpectedResponse: 403 Forbidden
```

Fix: Check QDRANT_API_KEY is correct and has appropriate permissions

### Health Checks

Render automatically monitors health endpoints:

**Backend**: `GET /health`

```json
{
  "status": "healthy",
  "qdrant_connected": true
}
```

**Frontend**: `GET /` (should return HTML)

### Performance Monitoring

1. **Render Dashboard** → Service → **"Metrics"**
   - CPU usage
   - Memory usage
   - Request count
   - Response time

2. **Set Auto-Scaling** (Pro plans):
   - Minimum instances: 1
   - Maximum instances: 3
   - Scale up when CPU > 80%

### Database Monitoring (Qdrant)

1. Access Qdrant Dashboard: https://console.qdrant.io/
2. Monitor:
   - Collection sizes
   - Query latency
   - Storage usage

---

## Deployment Checklist

- [ ] All environment variables configured in Render
- [ ] Backend service created and building successfully
- [ ] Frontend service created and building successfully
- [ ] Backend `/health` endpoint returns healthy status
- [ ] Frontend loads without JavaScript errors
- [ ] File upload functionality works end-to-end
- [ ] RFP processing streams responses correctly
- [ ] Compliance matrix displays properly
- [ ] API response times are acceptable (<3s)
- [ ] No console errors in browser DevTools
- [ ] PDF export functionality works
- [ ] Dark mode (if applicable) works correctly

---

## Scaling & Optimization

### For Production Traffic

**Backend Scaling**

- Increase instance type to Professional (1 CPU, 2GB RAM)
- Enable auto-scaling
- Consider load balancer for multiple instances

**Frontend Scaling**

- Enable caching for static assets
- Use CDN for global distribution (via custom domain)
- Implement ISR (Incremental Static Regeneration)

**Database Scaling**

- Monitor Qdrant collection sizes
- Implement retention policies
- Use pagination for large result sets

### Cost Optimization

- **Render Free Tier**: ~$7/month per service
- **Render Pro**: ~$7/month per service for better resources
- **Qdrant Cloud**: Pay-per-use starting at free tier

---

## Rollback & Recovery

### Rollback to Previous Version

1. Render Dashboard → Service
2. **"Logs"** tab → Find previous successful deployment
3. Click deployment → **"Redeploy"**

### Manual Deployment Trigger

```bash
git push origin main
# Render auto-deploys on push
```

### Clear Deployment Cache

- Service → **"Settings"** → **"Clear Build Cache"**
- Then redeploy

---

## Support & Debugging

### Get Backend Logs

```bash
curl https://vegah-backend.onrender.com/logs
```

### Test API Directly

```bash
# Health check
curl https://vegah-backend.onrender.com/health

# Upload capabilities
curl -F "file=@capabilities.csv" \
  https://vegah-backend.onrender.com/api/upload-capabilities
```

### Frontend Debugging

- Open DevTools (F12)
- Network tab: Check API request URLs
- Console: Look for errors
- Application tab: Check environment variables in browser

---

## Next Steps

1. Deploy to Render using steps above
2. Test all features in staging environment
3. Set up monitoring alerts
4. Configure custom domain
5. Enable SSL/TLS (automatic on Render)
6. Set up scheduled backups for Qdrant data
