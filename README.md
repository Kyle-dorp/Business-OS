# 🍰 BAMs CAKE POS → Google Sheets Dashboard

**Track your closing breakdown automatically. Know where your money is going.**

A complete integration that:
- ✅ Auto-captures closing data every time you close register
- ✅ Stores everything in Google Sheets (easy collaboration)
- ✅ Shows budget vs. actual in real-time
- ✅ Works with one login (manager view)
- ✅ Zero manual data entry

---

## 📁 What's Included

```
bams-cake-pos/
├── webhook-server.js          # The webhook listener & CAKE API client
├── package.json               # Node.js dependencies
├── .env.example               # Configuration template
├── dashboard.html             # Web dashboard (optional)
├── README.md                  # This file
├── cake-pos-setup-guide.md    # Getting started guide
├── google-sheets-setup.md     # Google Sheets configuration
└── deployment-guide.md        # Where & how to host
```

---

## 🚀 Quick Start (5 Steps)

### 1. Set Up Google Cloud (15 min)
- Create Google Cloud project
- Enable Sheets API
- Create service account & download JSON key
- Create Google Sheet & share with service account

**📖 Guide:** [google-sheets-setup.md](google-sheets-setup.md)

### 2. Get CAKE API Credentials (tomorrow at shop)
- Go to CAKE Settings
- Find API section
- Generate API key
- Note Location ID

**📖 Guide:** [cake-pos-setup-guide.md](cake-pos-setup-guide.md)

### 3. Configure & Deploy Server (20 min)
- Copy `.env.example` → `.env`
- Fill in all credentials
- Deploy to Replit/Heroku/Railway (or self-host)
- Test health endpoint

**📖 Guide:** [deployment-guide.md](deployment-guide.md)

### 4. Register Webhook in CAKE (5 min)
- Go to CAKE integrations
- Add webhook
- Paste your server URL
- Set event to "register close"

### 5. Test It! (5 min)
- Close a register in CAKE
- Check Google Sheet
- See data appear automatically ✨

---

## 📊 What Gets Tracked

From CAKE's closing breakdown, you'll automatically capture:

**Sales Data:**
- Total sales
- Sales by payment type (cash, card, etc.)
- Discounts applied
- Refunds issued
- Voids

**Cash Handling:**
- Cash in
- Cash out
- Cash variance (discrepancies)

**Analysis:**
- Comparison to daily budget
- Performance trends
- Payment type breakdown
- Deduction summary

---

## 💰 Budget Tracking

**How it works:**
1. Set your daily budget in Google Sheet
2. Close register normally
3. Data syncs automatically
4. Dashboard shows: **"You're at 87% of budget"** or **"$300 over target"**

**Example:**
- Daily budget target: $3,200
- Today's actual: $2,800
- Status: ⚠️ Under budget by $400

---

## 👥 Manager Access

Everything is shared in **one Google Sheet**:
- **Tab 1:** Daily Closings (raw data)
- **Tab 2:** Budget Tracking (analysis)
- **Tab 3:** Dashboard (summary)

Manager can:
- ✓ View closing details anytime
- ✓ See trends and patterns
- ✓ Check budget progress
- ✓ Export data for reporting
- ✓ Add notes or flags issues

---

## 🛠️ Technical Overview

### How It Works:

```
CAKE POS Register Close
        ↓
   Webhook Trigger
        ↓
  Node.js Server (Your Webhook Receiver)
        ↓
  Fetch Data from CAKE API
        ↓
  Parse & Transform Data
        ↓
  Write to Google Sheets
        ↓
  Dashboard Auto-Updates
```

### Stack:
- **Runtime:** Node.js
- **API Client:** Axios (calls CAKE API)
- **Sheets:** Google Sheets API
- **Hosting:** Replit / Heroku / Railway (or self-hosted)
- **Dashboard:** HTML + Chart.js (or your own)

---

## 📋 File Breakdown

| File | Purpose |
|------|---------|
| `webhook-server.js` | Main server. Listens for CAKE webhook, pulls data, writes to Sheets |
| `package.json` | Lists required Node packages |
| `.env.example` | Template for your credentials (copy to `.env`) |
| `dashboard.html` | Optional web dashboard for quick viewing |
| `cake-pos-setup-guide.md` | How to get CAKE API credentials |
| `google-sheets-setup.md` | How to set up Google Sheets structure |
| `deployment-guide.md` | How to deploy the server |

---

## 🔐 Security

**What's protected:**
- CAKE API key stored in `.env` (not in code)
- Google credentials stored as environment variable
- Webhook validation with secret token
- Service account has limited Sheets access only

**Best practices:**
- ✅ Never commit `.env` to git
- ✅ Use strong `WEBHOOK_SECRET`
- ✅ Regenerate API keys if compromised
- ✅ Restrict service account to specific sheet only

---

## 🧪 Testing

### Test Health:
```bash
curl https://your-domain.com/health
```

### Manual Close Entry (for testing):
```bash
curl -X POST https://your-domain.com/manual-close \
  -H "Content-Type: application/json" \
  -d '{
    "total_sales": 2450.50,
    "cash_in": 1200,
    "card_in": 1250.50,
    "discounts": 45,
    "refunds": 20,
    "voids": 5,
    "cash_out": 1195
  }'
```

---

## 🐛 Troubleshooting

**Data not syncing?**
1. Check health endpoint: `https://your-domain.com/health`
2. Check server logs for errors
3. Verify webhook is registered in CAKE
4. Make sure service account email has sheet access

**Getting API errors?**
1. Check CAKE API credentials are correct
2. Verify API base URL is right
3. Test with manual `/manual-close` endpoint
4. Check CAKE API rate limits

**Sheet showing errors?**
1. Verify `GOOGLE_SHEET_ID` is correct
2. Make sure service account has Editor access
3. Check column headers match expected format
4. Look at server logs for Google API errors

---

## 📞 Support Resources

**CAKE POS:**
- Developer Docs: https://developer.cake.net/
- Support: https://support.getcake.com/
- API Docs: https://university.cake.net/

**Google Sheets API:**
- Docs: https://developers.google.com/sheets/api
- Node.js Client: https://github.com/googleapis/google-api-nodejs-client

---

## 📈 Future Enhancements

Possible additions (not included in this setup):

- ✨ Slack notifications ("Daily sales: $2,450")
- ✨ Email reports sent to manager
- ✨ Multi-location support (multiple stores)
- ✨ Historical trend analysis
- ✨ Cashier performance leaderboard
- ✨ Automatic alerts if under budget
- ✨ Mobile app for quick checking

---

## 💡 Tips & Tricks

**Budget Setting:**
- Use 3-month average as baseline
- Account for seasonal patterns (busy vs. slow months)
- Adjust for special events or promotions

**Data Analysis:**
- Look for patterns by day of week
- Compare cashier performance
- Track discount trends (why are they high?)
- Monitor cash variance (training issue?)

**Workflow:**
- Manager checks sheet every morning
- Identify issues early
- Use data to make staffing decisions
- Share with team for transparency

---

## 🚀 Deployment

**Recommended hosting:**
- **Replit** (easiest, $7/mo for 24/7)
- **Railway** ($5/mo, simple)
- **Heroku** ($5-14/mo, professional)
- **Self-hosted** (free if you have a server)

See [deployment-guide.md](deployment-guide.md) for full instructions.

---

## 📝 Checklist: Before Going Live

- [ ] Google Cloud project created
- [ ] Service account created & key downloaded
- [ ] Google Sheet created with tabs
- [ ] Sheet shared with service account
- [ ] CAKE API credentials obtained
- [ ] .env file filled with all credentials
- [ ] Server deployed and health endpoint working
- [ ] Webhook registered in CAKE settings
- [ ] Test close successful (data in sheet)
- [ ] Dashboard accessible
- [ ] Team trained on how to use

---

## 📞 Questions?

When you come back with CAKE API credentials, I can:
1. Help you finalize the webhook code with correct endpoints
2. Test the integration
3. Train you on using the dashboard
4. Set up any additional features you need

---

**Created:** 2026-08-05  
**Version:** 1.0  
**Status:** Ready for setup
