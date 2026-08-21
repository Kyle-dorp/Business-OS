import express from 'express';
import { pool } from '../index';
import { certAuthMiddleware } from '../middleware/cert-auth';

const router = express.Router();

// Get dashboard summary
router.get('/summary', certAuthMiddleware, async (req, res) => {
  try {
    const today = new Date().toISOString().split('T')[0];

    // Get today's closing data
    const closingResult = await pool.query(
      'SELECT * FROM daily_closings WHERE date = $1',
      [today]
    );

    // Get today's tips
    const tipsResult = await pool.query(
      'SELECT SUM(total_tips) as total_tips FROM tips WHERE date = $1',
      [today]
    );

    // Get payroll summary
    const payrollResult = await pool.query(
      `SELECT COUNT(*) as total_employees, SUM(total_owed) as total_payroll_owed
       FROM payroll WHERE status = 'pending'`
    );

    // Get budget target
    const budgetResult = await pool.query(
      'SELECT daily_target FROM budget_targets WHERE date = $1',
      [today]
    );

    res.json({
      date: today,
      closing: closingResult.rows[0] || null,
      tips: tipsResult.rows[0],
      payroll: payrollResult.rows[0],
      budget: budgetResult.rows[0] || { daily_target: 5000 },
    });
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch dashboard summary' });
  }
});

// Get weekly summary
router.get('/weekly', certAuthMiddleware, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT
        date,
        total_sales,
        cash_in,
        card_in,
        discounts,
        refunds,
        voids
       FROM daily_closings
       WHERE date >= CURRENT_DATE - INTERVAL '7 days'
       ORDER BY date DESC`
    );
    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch weekly data' });
  }
});

// Get monthly summary
router.get('/monthly', certAuthMiddleware, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT
        DATE_TRUNC('month', date) as month,
        SUM(total_sales) as total_sales,
        SUM(cash_in) as cash_in,
        SUM(card_in) as card_in,
        SUM(discounts) as discounts,
        SUM(refunds) as refunds,
        COUNT(*) as days
       FROM daily_closings
       WHERE date >= CURRENT_DATE - INTERVAL '3 months'
       GROUP BY DATE_TRUNC('month', date)
       ORDER BY month DESC`
    );
    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch monthly data' });
  }
});

export default router;
