# Deployment Guide: Webhook Server

Your webhook server needs to be hosted somewhere that:
1. ✅ Has a public URL (so CAKE can reach it)
2. ✅ Stays online 24/7
3. ✅ Can handle environment variables
4. ✅ Runs Node.js

## Option 1: Replit (Easiest - FREE)

### Setup:
1. Go to **https://replit.com**
2. Click **Create** → **Import from GitHub**
3. Paste: `https://github.com/yourusername/bams-cake-pos` (after you push code there)
   - OR upload files manually
4. Replit will auto-detect `package.json` and install dependencies
5. Click **Run** button

### Configure Environment Variables:
1. Click **Secrets** (padlock icon, left panel)
2. Add each variable:
   - `CAKE_API_KEY`
   - `CAKE_API_URL`
   - `CAKE_LOCATION_ID`
   - `GOOGLE_SHEET_ID`
   - `GOOGLE_CREDENTIALS` (the full JSON)
   - `WEBHOOK_SECRET`

### Your Public URL:
- Replit gives you: `https://your-project-name.username.repl.co`
- Use this for CAKE webhook registration

### Keep it Running:
- Free tier: You need to keep the browser tab open
- Paid tier ($7/mo): Runs 24/7 with uptime monitoring
- **Recommended for this use case**

---

## Option 2: Heroku (Popular - FREE tier ending)

⚠️ Note: Heroku is discontinuing free tier. Paid dyno starts at $5/month.

### Setup:
1. Go to **https://www.heroku.com**
2. Create account and download **Heroku CLI**
3. Push code to Heroku:
   ```bash
   heroku login
   heroku create bams-cake-pos
   heroku config:set CAKE_API_KEY=xxx
   heroku config:set CAKE_API_URL=xxx
   # ... set all env vars
   git push heroku main
   ```

### Your Public URL:
- `https://bams-cake-pos.herokuapp.com`

---

## Option 3: Railway.app (Good - $5+ starter plan)

Simple alternative to Heroku.

### Setup:
1. Go to **https://railway.app**
2. Connect GitHub (or upload files)
3. Add environment variables in dashboard
4. Deploy — auto-generates URL

### Your Public URL:
- `https://your-service-name.railway.app`

---

## Option 4: Self-Hosted (If you have a server)

### Setup:
```bash
# SSH into your server
ssh user@your-server.com

# Clone code
git clone https://github.com/yourusername/bams-cake-pos
cd bams-cake-pos

# Install dependencies
npm install

# Create .env file
nano .env
# Paste all your credentials

# Run with PM2 (keeps it running)
npm install -g pm2
pm2 start webhook-server.js --name "bams-cake-pos"
pm2 startup  # Makes it restart on server reboot
pm2 save
```

### Your Public URL:
- `https://your-domain.com/webhook/cake/register-close`
- (or just `http://your-server-ip:3000/...` if no domain)

---

## Setup CAKE Webhook Registration

Once you have your server URL, register it in CAKE:

### In CAKE Settings:
1. Go to **Settings** → **Integrations** (or **Webhooks**)
2. Click **Add Webhook** or **Create Integration**
3. Configure:
   - **Webhook URL**: `https://your-domain.com/webhook/cake/register-close`
   - **Event Type**: `register.closed` or `daily.close` (check CAKE docs)
   - **Secret**: Paste your `WEBHOOK_SECRET` from .env
4. **Test Webhook** (if available)
5. Save

---

## Testing Your Setup

### 1. Test Server is Running:
```bash
curl https://your-domain.com/health
# Should return: {"status":"ok","timestamp":"2026-08-05T..."}
```

### 2. Test Manual Close:
```bash
curl -X POST https://your-domain.com/manual-close \
  -H "Content-Type: application/json" \
  -d '{
    "cashier_name": "John",
    "register_id": "1",
    "total_sales": 2450.50,
    "cash_in": 1200,
    "card_in": 1250.50,
    "discounts": 45,
    "refunds": 20,
    "voids": 5,
    "cash_out": 1195
  }'
```

### 3. Check Google Sheet:
- Open your sheet
- Look at **Daily Closings** tab
- Should see new row with data above

---

## Monitoring & Logs

### Replit:
- Click **Logs** tab at top
- Watch real-time output

### Heroku:
```bash
heroku logs --tail
```

### Railway:
- Dashboard shows logs automatically

### Self-hosted (PM2):
```bash
pm2 logs bams-cake-pos
```

---

## Environment Variables Checklist

Before deploying, make sure you have:

- [ ] `CAKE_API_KEY` (from CAKE settings)
- [ ] `CAKE_API_URL` (usually `https://api.trycake.com`)
- [ ] `CAKE_LOCATION_ID` (your store ID in CAKE)
- [ ] `GOOGLE_SHEET_ID` (from your Google Sheet URL)
- [ ] `GOOGLE_CREDENTIALS` (entire service account JSON)
- [ ] `WEBHOOK_SECRET` (random string you create)
- [ ] `PORT` (default: 3000, usually auto-detected by platform)
- [ ] `NODE_ENV` (set to `production`)

---

## Production Checklist

Before going live:

- [ ] All environment variables set
- [ ] CAKE webhook registered with correct URL
- [ ] Manual test successful (data appears in sheet)
- [ ] Google Sheet shared with service account
- [ ] Dashboard HTML deployed or accessible
- [ ] Error notifications set up (optional)
- [ ] Backup process for sheets data
- [ ] Team trained on how to use dashboard

---

## Common Issues

**Webhook not triggering?**
- Check CAKE has correct webhook URL
- Verify `WEBHOOK_SECRET` matches in .env
- Test with `/health` endpoint first

**Data not appearing in Sheet?**
- Check service account email has access
- Look at server logs for API errors
- Verify `GOOGLE_SHEET_ID` is correct

**Server keeps crashing?**
- Check logs for errors
- Verify all required environment variables are set
- Make sure `package.json` dependencies are installed

**Getting "Authentication Failed"?**
- Check `GOOGLE_CREDENTIALS` JSON is valid
- Make sure sheet is shared with service account email
- Verify service account has Editor access

---

## Cost Breakdown

| Platform | Cost | Best For |
|----------|------|----------|
| Replit | Free (limited) / $7/mo | Testing, low usage |
| Heroku | $5-14/mo | Professional, reliable |
| Railway | $5/mo minimum | Simple deployment |
| Self-hosted | $0-50/mo | Full control, existing server |

---

## Next: Connect to CAKE

Once server is running and tested:
1. Go to CAKE Settings
2. Register webhook with your public URL
3. Close a register in CAKE
4. Data should appear in Google Sheet
5. Dashboard auto-updates

You're live! 🚀
