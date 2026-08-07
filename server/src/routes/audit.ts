import express from 'express';
import { pool } from '../index';
import { certAuthMiddleware } from '../middleware/cert-auth';

const router = express.Router();

// Get audit logs
router.get('/', certAuthMiddleware, async (req, res) => {
  try {
    const limit = req.query.limit ? parseInt(req.query.limit as string) : 100;
    const result = await pool.query(
      `SELECT id, action, table_name, record_id, user_id, changes, ip_address, timestamp
       FROM audit_log
       ORDER BY timestamp DESC
       LIMIT $1`,
      [limit]
    );
    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch audit logs' });
  }
});

// Get audit logs by date range
router.get('/range/:startDate/:endDate', certAuthMiddleware, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT id, action, table_name, record_id, user_id, changes, ip_address, timestamp
       FROM audit_log
       WHERE timestamp::date BETWEEN $1 AND $2
       ORDER BY timestamp DESC`,
      [req.params.startDate, req.params.endDate]
    );
    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch audit logs' });
  }
});

// Clear audit logs (with confirmation)
router.post('/clear', certAuthMiddleware, async (req, res) => {
  const { days_to_keep } = req.body;

  if (typeof days_to_keep !== 'number' || days_to_keep < 0) {
    return res.status(400).json({ error: 'Invalid days_to_keep parameter' });
  }

  try {
    const result = await pool.query(
      `DELETE FROM audit_log
       WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '1 day' * $1`,
      [days_to_keep]
    );

    res.json({
      message: 'Audit logs cleared',
      rows_deleted: result.rowCount,
      kept_days: days_to_keep,
    });
  } catch (error) {
    res.status(500).json({ error: 'Failed to clear audit logs' });
  }
});

export default router;
