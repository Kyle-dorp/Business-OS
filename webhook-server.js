/**
 * CAKE POS Webhook Receiver → Google Sheets
 * Listens for register close events and logs closing breakdown to Google Sheets
 */

const express = require('express');
const { google } = require('googleapis');
const axios = require('axios');
require('dotenv').config();

const app = express();
app.use(express.json());

// ========================================
// CONFIGURATION - UPDATE WITH YOUR CREDENTIALS
// ========================================

const CONFIG = {
  // CAKE POS API Credentials (get from CAKE settings)
  CAKE_API_KEY: process.env.CAKE_API_KEY || 'your-cake-api-key-here',
  CAKE_API_URL: process.env.CAKE_API_URL || 'https://api.trycake.com', // Update with actual CAKE URL
  CAKE_LOCATION_ID: process.env.CAKE_LOCATION_ID || 'your-location-id',

  // Google Sheets
  GOOGLE_SHEET_ID: process.env.GOOGLE_SHEET_ID || 'your-sheet-id-here',
  GOOGLE_CREDENTIALS: process.env.GOOGLE_CREDENTIALS || null, // JSON stringified service account key

  // Webhook validation
  WEBHOOK_SECRET: process.env.WEBHOOK_SECRET || 'your-webhook-secret',

  // Server
  PORT: process.env.PORT || 3000,
};

// ========================================
// GOOGLE SHEETS SETUP
// ========================================

let sheets = null;

async function initializeSheets() {
  try {
    let credentials;

    if (!CONFIG.GOOGLE_CREDENTIALS) {
      throw new Error('GOOGLE_CREDENTIALS environment variable not set');
    }

    // Try to parse as JSON
    try {
      credentials = JSON.parse(CONFIG.GOOGLE_CREDENTIALS);
    } catch (parseError) {
      // If parsing fails, log debug info
      console.error('✗ Failed to parse GOOGLE_CREDENTIALS as JSON');
      console.error('First 50 chars:', CONFIG.GOOGLE_CREDENTIALS.substring(0, 50));
      throw parseError;
    }

    if (!credentials || !credentials.private_key) {
      throw new Error('GOOGLE_CREDENTIALS missing or invalid - no private_key found');
    }

    const auth = new google.auth.GoogleAuth({
      credentials,
      scopes: ['https://www.googleapis.com/auth/spreadsheets'],
    });

    sheets = google.sheets({ version: 'v4', auth });
    console.log('✓ Google Sheets connected');
  } catch (error) {
    console.error('✗ Google Sheets auth failed:', error.message);
  }
}

// ========================================
// CAKE POS API FUNCTIONS
// ========================================

/**
 * Fetch closing breakdown from CAKE API
 * You'll need to find the correct endpoint in CAKE's API docs
 */
async function getClosingBreakdown(registerId, date) {
  try {
    // TODO: Update this with actual CAKE endpoint
    // This is a placeholder - CAKE's endpoint might be:
    // /registers/{registerId}/close
    // /reports/daily-close
    // /closings/{registerId}
    // Check: https://developer.cake.net/

    const response = await axios.get(
      `${CONFIG.CAKE_API_URL}/api/registers/${registerId}/close`,
      {
        params: {
          date,
          apiKey: CONFIG.CAKE_API_KEY,
        },
        headers: {
          Authorization: `Bearer ${CONFIG.CAKE_API_KEY}`,
          'Content-Type': 'application/json',
        },
      }
    );

    return response.data;
  } catch (error) {
    console.error('✗ Failed to fetch CAKE closing data:', error.message);
    throw error;
  }
}

// ========================================
// GOOGLE SHEETS WRITE FUNCTIONS
// ========================================

/**
 * Append closing data to "Daily Closings" sheet
 */
async function appendClosingToSheet(closingData) {
  if (!sheets) {
    console.error('Google Sheets not initialized');
    return;
  }

  try {
    // Extract data from CAKE response
    // Adjust these fields based on CAKE's actual response structure
    const row = [
      new Date().toISOString().split('T')[0], // Date
      closingData.cashier_name || 'N/A', // Cashier
      closingData.register_id || 'N/A', // Register
      closingData.total_sales || 0, // Total Sales
      closingData.cash_in || 0, // Cash In
      closingData.card_in || 0, // Card In
      closingData.discounts || 0, // Discounts
      closingData.refunds || 0, // Refunds
      closingData.voids || 0, // Voids
      closingData.cash_out || 0, // Cash Out
      (closingData.cash_out - closingData.cash_in) || 0, // Variance
      closingData.notes || '', // Notes
    ];

    await sheets.spreadsheets.values.append({
      spreadsheetId: CONFIG.GOOGLE_SHEET_ID,
      range: 'Daily Closings!A:L', // Adjust columns as needed
      valueInputOption: 'USER_ENTERED',
      requestBody: {
        values: [row],
      },
    });

    console.log('✓ Data appended to Google Sheet:', row);
  } catch (error) {
    console.error('✗ Failed to append to sheet:', error.message);
  }
}

// ========================================
// WEBHOOK ENDPOINT
// ========================================

/**
 * POST /webhook/cake/register-close
 * Called by CAKE when a register closes
 */
app.post('/webhook/cake/register-close', async (req, res) => {
  try {
    console.log('📩 Webhook received:', req.body);

    // Validate webhook (optional security check)
    if (req.body.secret !== CONFIG.WEBHOOK_SECRET) {
      console.warn('⚠ Webhook validation failed');
      return res.status(401).json({ error: 'Unauthorized' });
    }

    const { register_id, cashier_name, closing_time } = req.body;

    // 1. Fetch closing breakdown from CAKE
    const closingData = await getClosingBreakdown(register_id, new Date());

    // 2. Append to Google Sheet
    await appendClosingToSheet({
      ...closingData,
      cashier_name,
      register_id,
    });

    // 3. Success response
    res.json({
      success: true,
      message: 'Closing data recorded',
      data: closingData,
    });

    console.log('✓ Webhook processed successfully');
  } catch (error) {
    console.error('✗ Webhook processing failed:', error);
    res.status(500).json({ error: error.message });
  }
});

// ========================================
// HEALTH CHECK ENDPOINT
// ========================================

app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
  });
});

// ========================================
// MANUAL TRIGGER (for testing)
// ========================================

app.post('/manual-close', async (req, res) => {
  try {
    console.log('🔄 Manual close triggered');
    const testData = req.body || {};

    await appendClosingToSheet(testData);
    res.json({ success: true, message: 'Data recorded' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// ========================================
// STARTUP
// ========================================

async function start() {
  await initializeSheets();

  app.listen(CONFIG.PORT, () => {
    console.log(`
╔════════════════════════════════════════════╗
║   CAKE POS → Google Sheets Webhook Receiver║
║   Port: ${CONFIG.PORT}
║   Status: 🟢 Ready
╚════════════════════════════════════════════╝

Webhook URL: https://your-domain.com/webhook/cake/register-close
Health Check: https://your-domain.com/health
Manual Test: POST https://your-domain.com/manual-close

Environment Variables Needed:
- CAKE_API_KEY
- CAKE_API_URL
- CAKE_LOCATION_ID
- GOOGLE_SHEET_ID
- GOOGLE_CREDENTIALS (JSON stringified)
- WEBHOOK_SECRET
    `);
  });
}

start();

module.exports = app;
