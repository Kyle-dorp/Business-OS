import express from 'express';
import { pool } from '../index';
import { certAuthMiddleware } from '../middleware/cert-auth';

const router = express.Router();

// Get all tips
router.get('/', certAuthMiddleware, async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT * FROM tips ORDER BY date DESC'
    );
    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch tips' });
  }
});

// Create tip record
router.post('/', certAuthMiddleware, async (req, res) => {
  const { date, total_tips, note, splits } = req.body;

  if (!date || !total_tips) {
    return res.status(400).json({ error: 'Missing required fields' });
  }

  try {
    const tipResult = await pool.query(
      `INSERT INTO tips (date, total_tips, note)
       VALUES ($1, $2, $3)
       RETURNING *`,
      [date, total_tips, note]
    );

    const tipId = tipResult.rows[0].id;

    // Insert tip splits if provided
    if (splits && splits.length > 0) {
      for (const split of splits) {
        await pool.query(
          `INSERT INTO tips_split (tip_id, employee_id, amount)
           VALUES ($1, $2, $3)`,
          [tipId, split.employee_id, split.amount]
        );
      }
    }

    res.status(201).json(tipResult.rows[0]);
  } catch (error) {
    console.error('Error creating tip record:', error);
    res.status(500).json({ error: 'Failed to create tip record' });
  }
});

// Get tips for specific date
router.get('/:date', certAuthMiddleware, async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT * FROM tips WHERE date = $1',
      [req.params.date]
    );
    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch tips' });
  }
});

export default router;
