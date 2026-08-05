# Google Sheets Setup Guide

## 📋 Create Your Closing Tracking Sheet

### Step 1: Create a New Google Sheet

1. Go to **https://sheets.google.com**
2. Click **+ (Create)** → **Blank Spreadsheet**
3. Name it: `BAMs Daily Closing` (or whatever you prefer)
4. You'll need the **Sheet ID** from the URL: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit`

---

## 📊 Sheet Structure

### Tab 1: `Daily Closings` (Raw Data)

This is where all your closing data will be automatically logged.

**Column Headers (Row 1):**

| A | B | C | D | E | F | G | H | I | J | K | L |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Date | Cashier | Register | Total Sales | Cash In | Card In | Discounts | Refunds | Voids | Cash Out | Variance | Notes |

**Format:**
- **A: Date** — Format as `MM/DD/YYYY`
- **B: Cashier** — Name of person who closed
- **C: Register** — Register number
- **D: Total Sales** — Currency format
- **E: Cash In** — Currency format
- **F: Card In** — Currency format
- **G: Discounts** — Currency format
- **H: Refunds** — Currency format
- **I: Voids** — Currency format
- **J: Cash Out** — Currency format
- **K: Variance** — Formula: `=J2-E2` (will calculate automatically)
- **L: Notes** — Text (any notes about the close)

**Example Row 2:**
| 08/05/2026 | John | 1 | $2,450.50 | $1,200.00 | $1,250.50 | $45.00 | $20.00 | $5.00 | $1,195.00 | -$5.00 | ✓ All clear |

---

### Tab 2: `Budget Tracking` (Analysis & Trends)

Manual or formula-based tracking of performance vs. budget.

**Column Headers:**

| A | B | C | D | E | F |
|---|---|---|---|---|---|
| Date | Daily Budget | Actual Sales | Variance | % of Target | Status |

**Formulas:**
- **D: Variance** = `=C2-B2` (Actual - Budget)
- **E: % of Target** = `=C2/B2*100` (shows as percentage)
- **F: Status** = `=IF(C2>=B2, "✓ On Track", "⚠ Under Budget")`

---

### Tab 3: `Dashboard` (Summary View)

Quick reference for today/this week/this month.

**Cell Layout (Manual Update or Formulas):**

```
┌─────────────────────────────────────┐
│  TODAY'S CLOSING SUMMARY            │
├─────────────────────────────────────┤
│ Total Sales:        $2,450.50       │
│ Daily Budget:       $2,800.00       │
│ Progress:           87% ✓           │
│ Cash Variance:      -$5.00          │
├─────────────────────────────────────┤
│ PAYMENT BREAKDOWN                   │
│ Cash:               $1,200.00       │
│ Card:               $1,250.50       │
│ Other:              $0.00           │
├─────────────────────────────────────┤
│ DEDUCTIONS                          │
│ Discounts:          $45.00          │
│ Refunds:            $20.00          │
│ Voids:              $5.00           │
│ Total Deductions:   $70.00          │
└─────────────────────────────────────┘
```

**Formulas to use:**
- Get TODAY's data: `=FILTER('Daily Closings'!A:L, 'Daily Closings'!A:A=TODAY())`
- Sum THIS WEEK: `=SUMIFS('Daily Closings'!D:D, 'Daily Closings'!A:A, ">="&TODAY()-WEEKDAY(TODAY(),3))`
- Average DAILY: `=AVERAGE('Daily Closings'!D:D)`

---

## 🔑 Google Cloud Service Account Setup

This allows the webhook server to write data to your sheet.

### 1. Create Service Account

1. Go to **https://console.cloud.google.com**
2. Create a new project called `BAMs POS Integration`
3. Enable these APIs:
   - **Google Sheets API**
   - **Google Drive API**

### 2. Create Service Account Key

1. Go to **APIs & Services** → **Service Accounts** (left sidebar)
2. Click **Create Service Account**
3. Name: `cake-pos-integration`
4. Click **Create and Continue**
5. Under **Keys** tab:
   - Click **Add Key** → **Create new key**
   - Choose **JSON**
   - This downloads a `.json` file — **SAVE IT SECURELY**

### 3. Share Sheet with Service Account

1. Open the downloaded JSON file
2. Find the `client_email` field (looks like `cake-pos-integration@...iam.gserviceaccount.com`)
3. Copy it
4. Go to your Google Sheet
5. Click **Share** (top right)
6. Paste the service account email
7. Give it **Editor** access
8. Click **Share**

---

## 🚀 Connect to Webhook Server

Once you have your credentials:

1. **Copy the entire service account JSON** (open the file in Notepad)
2. **Paste into `.env`** file as `GOOGLE_CREDENTIALS`
3. **Get your Sheet ID** from the URL
4. **Paste into `.env`** as `GOOGLE_SHEET_ID`
5. **Deploy the webhook server** (Heroku, Replit, etc.)
6. **Register webhook in CAKE** with your server URL

---

## 📱 Optional: Google Sheets Mobile App

You can view/edit this sheet from:
- **Mobile**: Google Sheets app (iOS/Android)
- **Desktop**: https://sheets.google.com
- **Dashboard**: The separate HTML dashboard we created

---

## 🔄 Daily Workflow

### For You (Cashier/Owner):
1. Close register normally in CAKE
2. CAKE sends webhook → data automatically appears in Google Sheet
3. Check the dashboard anytime: `https://your-domain.com/dashboard`

### For Manager:
1. Open shared Google Sheet
2. Check "Daily Closings" tab for details
3. Check "Budget Tracking" tab for trends
4. Check "Dashboard" tab for quick summary

---

## 🧮 Budget Tracking Best Practices

**Set Your Daily Budget:**
- In "Budget Tracking" sheet, set a realistic daily target
- Example: If monthly goal is $80,000 ÷ 25 business days = $3,200/day
- Adjust seasonally (busy days vs. slow days)

**Monitor Variance:**
- **Positive variance** = You're ahead of budget (good!)
- **Negative variance** = You're behind budget (adjust operations)
- Look for patterns: certain days, certain cashiers, payment types

**Key Metrics to Watch:**
- Total Sales vs. Budget
- Cash variance (discrepancies)
- Discount/refund trends (indicate issues or promotions)
- Payment type distribution (cash vs. card trending)

---

## 🔗 Quick Reference

| What | Where | Access |
|------|-------|--------|
| Raw closing data | Daily Closings tab | Google Sheet |
| Budget tracking | Budget Tracking tab | Google Sheet |
| Quick summary | Dashboard tab | Google Sheet |
| Web dashboard | /dashboard | Browser |
| Manual data pull | /manual-close | Server API |
| Health check | /health | Server API |
| Webhook test | Webhook endpoint | CAKE settings |

---

## ⚠️ Troubleshooting

**Data not appearing in sheet?**
- Check webhook was registered in CAKE settings
- Verify service account email has sheet access
- Check server logs for errors

**Permission denied error?**
- Make sure you shared the sheet with service account email
- Check that service account has Editor access (not Viewer)

**Formulas not calculating?**
- Make sure column headers are exactly as specified
- Double-check formula syntax for your data layout
- Manual entry also works fine

---

## 📞 Next Steps

1. ✅ Create Google Sheet with tabs above
2. ✅ Set up Google Cloud project & service account
3. ✅ Download service account JSON key
4. ✅ Share sheet with service account
5. ⏳ Get CAKE API credentials (tomorrow)
6. ⏳ Deploy webhook server
7. ⏳ Register webhook in CAKE
8. 🚀 Start tracking!
