# CAKE POS → Google Sheets Dashboard Setup

## 📋 What We're Building
- **Webhook Receiver**: Auto-triggers when you close register
- **Google Sheets**: Real-time closing breakdown + budget tracking
- **Dashboard**: Web view of today's numbers + trends
- **1 Login**: Manager view (can see everything)

---

## 🔑 Step 1: Get Your CAKE POS API Credentials (Tomorrow)

When you go to the shop, get these from CAKE:

1. Go to **CAKE Settings** → **API/Integrations** (or similar)
2. Generate/copy:
   - **API Key** (or Client ID/Secret)
   - **API Base URL** (usually `https://api.cake.net` or similar)
3. Note your **Location ID** (from CAKE settings)

Also check if CAKE has:
- Webhook setup section (to register your webhook URL)
- Register Close event type (what event triggers your data pull)

### Resources to check:
- https://developer.cake.net/ (official API portal)
- https://university.cake.net/s/article/Close-Cash (how closing works in CAKE)
- https://support.getcake.com/support/solutions/5000109264 (API support)

---

## 🔐 Step 2: Google Cloud Setup (Do This Now)

### 2a. Create a Google Cloud Project
1. Go to **https://console.cloud.google.com**
2. Create a new project named `BAMs Dashboard`
3. Enable these APIs:
   - **Google Sheets API**
   - **Google Drive API**
4. Go to **Service Accounts** (left menu → APIs & Services → Service Accounts)
5. Create a new service account named `cake-pos-integration`
6. Create a **JSON key** for this service account → **SAVE THIS FILE SECURELY**

This key will authenticate your webhook receiver to write to Google Sheets.

### 2b. Create Google Sheet Template
1. Create a new Google Sheet named `BAMs Daily Closing`
2. Share it with your service account email (found in the JSON key)
3. We'll populate the sheet structure in the code setup

---

## 🔌 Step 3: Deploy Webhook Receiver

Your webhook receiver will:
- Listen for register close events from CAKE
- Call CAKE API to get full closing breakdown
- Parse the data
- Write to Google Sheets
- Send optional Slack/email notification

We'll host this using **Replit** (free), **Heroku** (free tier), or your own server.

---

## 📊 Step 4: Google Sheets Structure

Your sheet will have these tabs:

### Tab 1: `Daily Closings` (Raw Data)
- Date | Cashier | Register | Total Sales | Cash In | Card In | Discounts | Refunds | Voids | Cash Out | Variance | Notes

### Tab 2: `Budget Tracking` (Analysis)
- Date | Target Budget | Actual Sales | Variance | % of Target | Payment Breakdown | Top Category

### Tab 3: `Dashboard` (Summary)
- Today's totals
- This week's trend
- Budget progress
- Payment type breakdown (pie chart)

---

## 🔧 Implementation Steps

Once you have your CAKE API credentials tomorrow:

1. **Provide me with:**
   - CAKE API Key
   - CAKE API Base URL
   - Your Location ID
   - Google Sheets URL
   - Service Account JSON key file

2. **I'll provide:**
   - Complete Node.js webhook code
   - Google Sheets integration module
   - Dashboard HTML/React app
   - Deployment instructions

3. **You'll do:**
   - Register webhook URL in CAKE
   - Deploy the Node.js receiver
   - Set daily budget in Sheet
   - Close register normally (automation handles the rest)

---

## 💡 What Data You'll Track

From CAKE's closing breakdown, we'll capture:
- **Sales Metrics**: Total, by payment type (cash, card, etc.), discounts, voids, refunds
- **Cash Handling**: Cash in, cash out, variance
- **Performance**: Comparison to daily budget
- **Trends**: Weekly/monthly performance
- **Breakdown**: By category, cashier, shift (if available)

---

## 🎯 Budget Workflow

1. **Set Daily Budget** in Google Sheet
2. **Close register normally** → data syncs automatically
3. **Dashboard shows**: "You're at 87% of budget" or "On track/over"
4. **Manager can**: Check anytime, see trends, export reports

---

## Next Steps

1. ✅ Read this guide
2. ⏳ Go to shop tomorrow, get API credentials
3. 📞 Come back with credentials → I'll complete the setup
4. 🚀 Deploy and test
5. 📈 Start tracking

---

## Questions/Support

If you get stuck finding the API credentials:
- Check CAKE admin settings for "Integrations" or "Developers"
- Call CAKE support: they can enable API access for you
- Ask them specifically: "Can I get API credentials for a webhook integration?"
