import express from 'express';
import { pool } from '../index';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';

const router = express.Router();

/**
 * CAKE POS Webhook Receiver
 * POST /webhook/cake/register-close
 * Receives closing data when register closes
 */
router.post('/register-close', async (req, res) => {
  try {
    console.log('📩 CAKE Webhook received:', req.body);

    // Validate webhook secret if configured
    if (process.env.WEBHOOK_SECRET && req.body.secret !== process.env.WEBHOOK_SECRET) {
      console.warn('⚠ Webhook secret validation failed');
      return res.status(401).json({ error: 'Unauthorized' });
    }

    const {
      register_id,
      cashier_name,
      closing_time,
      total_sales,
      cash_in,
      card_in,
      discounts,
      refunds,
      voids,
      cash_out,
      notes,
    } = req.body;

    const today = new Date().toISOString().split('T')[0];
    const variance = (cash_out || 0) - (cash_in || 0);

    // Insert closing data
    const result = await pool.query(
      `INSERT INTO daily_closings (date, total_sales, cash_in, card_in, discounts, refunds, voids, cash_out, variance, notes)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
       ON CONFLICT (date) DO UPDATE SET
         total_sales = EXCLUDED.total_sales,
         cash_in = EXCLUDED.cash_in,
         card_in = EXCLUDED.card_in,
         discounts = EXCLUDED.discounts,
         refunds = EXCLUDED.refunds,
         voids = EXCLUDED.voids,
         cash_out = EXCLUDED.cash_out,
         variance = EXCLUDED.variance,
         notes = EXCLUDED.notes,
         updated_at = CURRENT_TIMESTAMP
       RETURNING *`,
      [today, total_sales, cash_in, card_in, discounts, refunds, voids, cash_out, variance, notes]
    );

    // Also log as transaction(s)
    if (total_sales) {
      await pool.query(
        `INSERT INTO transactions (date, type, amount, payment_method, description, source)
         VALUES ($1, $2, $3, $4, $5, $6)`,
        [today, 'sale', total_sales, 'mixed', `Register ${register_id} closing`, 'cake_pos']
      );
    }

    console.log('✓ Closing data recorded:', result.rows[0]);

    res.json({
      success: true,
      message: 'Closing data recorded',
      data: result.rows[0],
    });
  } catch (error) {
    console.error('✗ Webhook processing failed:', error);
    res.status(500).json({
      error: 'Failed to process webhook',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
});

/**
 * Manual closing entry
 * POST /webhook/cake/manual-close
 * For testing or manual entry
 */
router.post('/manual-close', async (req, res) => {
  try {
    const {
      date,
      total_sales,
      cash_in,
      card_in,
      discounts,
      refunds,
      voids,
      cash_out,
      notes,
    } = req.body;

    const variance = (cash_out || 0) - (cash_in || 0);

    const result = await pool.query(
      `INSERT INTO daily_closings (date, total_sales, cash_in, card_in, discounts, refunds, voids, cash_out, variance, notes)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
       ON CONFLICT (date) DO UPDATE SET
         total_sales = EXCLUDED.total_sales,
         cash_in = EXCLUDED.cash_in,
         card_in = EXCLUDED.card_in,
         discounts = EXCLUDED.discounts,
         refunds = EXCLUDED.refunds,
         voids = EXCLUDED.voids,
         cash_out = EXCLUDED.cash_out,
         variance = EXCLUDED.variance,
         notes = EXCLUDED.notes,
         updated_at = CURRENT_TIMESTAMP
       RETURNING *`,
      [date || new Date().toISOString().split('T')[0], total_sales, cash_in, card_in, discounts, refunds, voids, cash_out, variance, notes]
    );

    res.status(201).json({
      success: true,
      message: 'Closing data recorded',
      data: result.rows[0],
    });
  } catch (error) {
    res.status(500).json({ error: 'Failed to record closing' });
  }
});

export default router;
