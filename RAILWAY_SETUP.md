# Railway Deployment - Step by Step

## Prerequisites
- GitHub account with repo pushed
- Railway account (https://railway.app)
- Anthropic API key

## 🚀 Deploy in 5 Minutes

### 1. Push to GitHub
```bash
cd "D:\projects\KDB Innovations\business-eos"
git add .
git commit -m "feat: complete redesign - modular, minimal UI, AI chat"
git push origin main
```

### 2. Connect to Railway
1. Go to https://railway.app/dashboard
2. Click **+ New Project**
3. Select **Deploy from GitHub repo**
4. Authorize GitHub
5. Select your `business-eos` repo
6. Railway auto-detects services from `Dockerfile.api` and `frontend/Dockerfile`

### 3. Add PostgreSQL Database
1. In project, click **+ Add Service**
2. Select **Postgres**
3. Railway creates database automatically

### 4. Set Environment Variables

**For API service:**
```
JWT_SECRET=<generate-32-char-random-string>
ANTHROPIC_API_KEY=sk-proj-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
CORS_ORIGINS=https://<your-railway-domain>
VITE_API_URL=https://<your-railway-api-domain>
DATABASE_URL=<Railway auto-fills>
```

**For Frontend service:**
```
VITE_API_URL=https://<your-railway-api-domain>
```

### 5. Configure Services

**API Service:**
- Set start command: `alembic upgrade head && uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`
- Expose port: `8000`
- Add Postgres as dependency

**Frontend Service:**
- Expose port: `80` (or Railway default)
- Build command: `cd frontend && npm install && npm run build`

### 6. Deploy
- Railway auto-deploys on git push
- Wait 10-15 minutes for first deploy
- Check **Deployments** tab for status
- Visit your Railway domain when green ✅

---

## 🔐 Secret Management

Generate JWT_SECRET:
```bash
# Linux/Mac
openssl rand -base64 32

# Windows PowerShell
[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes((New-Guid).ToString())) | % { $_.Substring(0, 43) }
```

---

## 📊 After Deployment

1. **Test API**: `https://<your-api>.railway.app/docs`
2. **Test Frontend**: `https://<your-domain>.railway.app`
3. **Check logs**: Railway dashboard → Logs tab
4. **Monitor**: Railway provides CPU, memory, requests metrics

---

## 🆘 Troubleshooting

**Build fails:**
- Check `Dockerfile.api` exists
- Check `frontend/Dockerfile` exists
- View build logs in Railway dashboard

**API not connecting:**
- Verify `DATABASE_URL` is set
- Check `CORS_ORIGINS` includes frontend domain
- Check `VITE_API_URL` is correct in frontend env

**Frontend not loading:**
- Check build output in logs
- Verify `VITE_API_URL` environment variable
- Clear browser cache

---

## 💡 Pro Tips

1. **Use Railway Secrets** for sensitive data (API keys, DB passwords)
2. **Set health checks** so Railway auto-restarts on crash
3. **Enable log draining** to send logs to external service
4. **Use staging branch** for pre-production testing
5. **Monitor metrics** — Railway alerts on high resource usage

---

**Ready? Deploy now!** 🚀

Once deployed, you'll have:
- ✅ Modular business operations platform
- ✅ Clean, minimal UI with cyan accents
- ✅ AI chat bubble
- ✅ Admin panel for module management
- ✅ Production database (PostgreSQL)
- ✅ HTTPS + auto scaling

Visit your Railway domain to see it live!
