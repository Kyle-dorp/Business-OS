# Instant Deployment Guide

## 🚀 Railway Deployment (Recommended)

### Step 1: Prepare Your Git Repo
```bash
cd "D:\projects\KDB Innovations\business-eos"
git add .
git commit -m "feat: complete modular redesign with new UI"
git push origin main
```

### Step 2: Connect to Railway
1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub"
4. Connect your repo
5. Railway auto-detects `Dockerfile.api` and `frontend/Dockerfile`

### Step 3: Environment Variables
Set in Railway dashboard:
```
DATABASE_URL=postgresql://...  (Railway PostgreSQL)
JWT_SECRET=<generate-long-random-string>
ANTHROPIC_API_KEY=<your-key>
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
CORS_ORIGINS=https://your-domain.com
VITE_API_URL=https://your-api.railway.app
```

### Step 4: Deploy
- Railway auto-deploys on push
- Wait 5-10 minutes for build
- Visit `https://your-domain.railway.app`

---

## 🐳 Docker Local Deployment

### Build & Run
```bash
# Backend
docker build -f Dockerfile.api -t business-eos-api .
docker run -p 8000:8000 -e DATABASE_URL=sqlite:///./business.db business-eos-api

# Frontend (in another terminal)
cd frontend
docker build -f Dockerfile -t business-eos-frontend .
docker run -p 80:80 business-eos-frontend
```

Visit: `http://localhost`

---

## 🔧 Before Deploying

### Database Migration
```bash
# This MUST run before API starts
alembic upgrade head
```

### Environment Setup
Copy `.env.example` to `.env`:
```bash
DATABASE_URL=postgresql://user:pass@localhost/business_eos
JWT_SECRET=your-super-secret-key-here-minimum-32-chars
ANTHROPIC_API_KEY=sk-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
CORS_ORIGINS=http://localhost:5173,https://your-domain.com
VITE_API_URL=http://localhost:8000
```

---

## 🧪 Test After Deploy

1. **Visit homepage** — Should see sidebar + dashboard
2. **Check admin panel** — Click ⚙️ icon
3. **Test chat bubble** — Click cyan circle (bottom-right)
4. **Check network** — Open DevTools, should see `/api/modules/enabled` call

---

## ✅ Checklist

- [ ] Environment variables set
- [ ] Database migrated (`alembic upgrade head`)
- [ ] Docker images built
- [ ] Port 8000 (API) and 80 (frontend) available
- [ ] CORS configured correctly
- [ ] API running before frontend starts

**Deploy when ready!** 🚀
