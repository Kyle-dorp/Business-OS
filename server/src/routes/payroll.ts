import express from 'express';
import { pool } from '../index';
import { certAuthMiddleware, requireRole } from '../middleware/cert-auth';

const router = express.Router();

// Get all payroll records
router.get('/', certAuthMiddleware, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT p.*, e.name, e.email
       FROM payroll p
       JOIN employees e ON p.employee_id = e.id
       ORDER BY p.period_end DESC`
    );
    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch payroll' });
  }
});

// Get payroll for specific employee
router.get('/employee/:employeeId', certAuthMiddleware, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT * FROM payroll WHERE employee_id = $1 ORDER BY period_end DESC`,
      [req.params.employeeId]
    );
    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch employee payroll' });
  }
});

// Create/update payroll record
router.post('/', certAuthMiddleware, async (req, res) => {
  const { employee_id, period_start, period_end, hours, base_pay, tips, taxes_withheld } = req.body;

  const total_owed = (base_pay || 0) + (tips || 0) - (taxes_withheld || 0);

  try {
    const result = await pool.query(
      `INSERT INTO payroll (employee_id, period_start, period_end, hours, base_pay, tips, taxes_withheld, total_owed)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
       RETURNING *`,
      [employee_id, period_start, period_end, hours, base_pay, tips, taxes_withheld, total_owed]
    );
    res.status(201).json(result.rows[0]);
  } catch (error) {
    console.error('Error creating payroll:', error);
    res.status(500).json({ error: 'Failed to create payroll record' });
  }
});

// Update payroll record
router.put('/:id', certAuthMiddleware, async (req, res) => {
  const { hours, base_pay, tips, taxes_withheld, status } = req.body;
  const total_owed = (base_pay || 0) + (tips || 0) - (taxes_withheld || 0);

  try {
    const result = await pool.query(
      `UPDATE payroll
       SET hours = COALESCE($1, hours),
           base_pay = COALESCE($2, base_pay),
           tips = COALESCE($3, tips),
           taxes_withheld = COALESCE($4, taxes_withheld),
           total_owed = $5,
           status = COALESCE($6, status),
           updated_at = CURRENT_TIMESTAMP
       WHERE id = $7
       RETURNING *`,
      [hours, base_pay, tips, taxes_withheld, total_owed, status, req.params.id]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Payroll record not found' });
    }

    res.json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ error: 'Failed to update payroll' });
  }
});

export default router;
