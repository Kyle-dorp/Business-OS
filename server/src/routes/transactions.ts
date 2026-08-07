import express from 'express';
import { pool } from '../index';
import { certAuthMiddleware } from '../middleware/cert-auth';

const router = express.Router();

// Get all transactions
router.get('/', certAuthMiddleware, async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT * FROM transactions ORDER BY created_at DESC LIMIT 1000'
    );
    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch transactions' });
  }
});

// Get transactions by date range
router.get('/range/:startDate/:endDate', certAuthMiddleware, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT * FROM transactions
       WHERE date BETWEEN $1 AND $2
       ORDER BY date DESC`,
      [req.params.startDate, req.params.endDate]
    );
    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch transactions' });
  }
});

// Create transaction
router.post('/', certAuthMiddleware, async (req, res) => {
  const { date, type, amount, payment_method, employee_id, description, source } = req.body;

  try {
    const result = await pool.query(
      `INSERT INTO transactions (date, type, amount, payment_method, employee_id, description, source)
       VALUES ($1, $2, $3, $4, $5, $6, $7)
       RETURNING *`,
      [date, type, amount, payment_method, employee_id, description, source || 'manual']
    );
    res.status(201).json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ error: 'Failed to create transaction' });
  }
});

export default router;
