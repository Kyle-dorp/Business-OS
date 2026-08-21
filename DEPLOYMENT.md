# Business-EOS Deployment Guide

## Local Development

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
export DATABASE_URL=postgresql://user:pass@localhost/business_eos
export SECRET_KEY=your-secret-key
uvicorn app.main:app --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

### Database
Create a PostgreSQL database:
```bash
createdb business_eos
```

## Railway Deployment

### Prerequisites
1. Railway account (railway.app)
2. GitHub repository with this code
3. PostgreSQL database (Railway provides this)

### Deployment Steps

1. **Connect your repository to Railway**
   - Go to railway.app and create a new project
   - Connect your GitHub repository
   - Railway will auto-detect the Dockerfile

2. **Add PostgreSQL**
   - In Railway dashboard, add a PostgreSQL plugin
   - Railway automatically sets DATABASE_URL

3. **Set Environment Variables**
   ```
   SECRET_KEY=your-production-secret-key
   ADMIN_API_KEY=your-admin-api-key
   STRIPE_PUBLIC_KEY=pk_...
   STRIPE_SECRET_KEY=sk_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   OPENAI_API_KEY=sk-... (optional)
   CORS_ORIGINS=https://your-domain.com
   ```

4. **Deploy**
   - Railway automatically builds and deploys on push to main
   - Monitor deployment in Railway dashboard

### Database Migrations
On first deployment, the FastAPI startup event creates all tables automatically.

### Building Locally
```bash
# Build frontend
cd frontend
npm run build

# Creates /frontend/dist with production build
```

## Production Checklist

- [ ] Set SECRET_KEY to a strong random value
- [ ] Configure Stripe keys (if using billing)
- [ ] Set up email service (Sendgrid/Mailgun)
- [ ] Configure CORS_ORIGINS for your domain
- [ ] Set up monitoring/logging
- [ ] Configure backups for PostgreSQL
- [ ] Set up SSL certificate (Railway handles this)
- [ ] Test full auth flow
- [ ] Test all API endpoints
- [ ] Load test the deployment

## Troubleshooting

### Database Connection Error
- Check DATABASE_URL is set in Railway env vars
- Verify PostgreSQL plugin is added to project
- Check Railway logs for connection details

### Static Files Not Loading
- Verify frontend build succeeded: `npm run build`
- Check static/ directory exists in production
- Check CORS settings if assets from CDN

### API Endpoint Errors
- Check API logs in Railway
- Verify all env vars are set
- Check database connection
- Test with curl: `curl https://your-domain.com/health`

## Cost Estimates (Monthly)

- App dyno: ~$7-14/month
- PostgreSQL: ~$15-50/month (depending on size)
- Total: ~$22-64/month for basic deployment

## Scaling

For production scale:
- Use Railway's auto-scaling
- Add Redis for caching
- Set up CDN for static assets (Cloudflare)
- Use managed Postgres with read replicas
- Configure monitoring and alerts

## API Endpoints

### Public (No Auth)
- POST /auth/setup
- POST /auth/login
- GET /health

### Protected (Require Token)
- GET/POST/PATCH/DELETE for all resources
- Pass token: `Authorization: Bearer {token}`
- Pass business: `X-Business-Id: {id}`

## Support

For Railway-specific issues: https://railway.app/docs
For application issues: Check logs in Railway dashboard
