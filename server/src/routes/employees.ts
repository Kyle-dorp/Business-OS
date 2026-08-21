import express from 'express';
import { pool } from '../index';
import { certAuthMiddleware } from '../middleware/cert-auth';

const router = express.Router();

// Get all employees
router.get('/', certAuthMiddleware, async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT id, name, email, role, hourly_rate, is_active, created_at FROM employees ORDER BY name'
    );
    res.json(result.rows);
  } catch (error) {
    console.error('Error fetching employees:', error);
    res.status(500).json({ error: 'Failed to fetch employees' });
  }
});

// Get single employee
router.get('/:id', certAuthMiddleware, async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT id, name, email, role, hourly_rate, is_active, created_at FROM employees WHERE id = $1',
      [req.params.id]
    );
    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Employee not found' });
    }
    res.json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch employee' });
  }
});

// Create new employee
router.post('/', certAuthMiddleware, async (req, res) => {
  const { name, email, role, hourly_rate } = req.body;

  if (!name || !role || hourly_rate === undefined) {
    return res.status(400).json({ error: 'Missing required fields' });
  }

  try {
    const result = await pool.query(
      `INSERT INTO employees (name, email, role, hourly_rate)
       VALUES ($1, $2, $3, $4)
       RETURNING id, name, email, role, hourly_rate, created_at`,
      [name, email, role, hourly_rate]
    );
    res.status(201).json(result.rows[0]);
  } catch (error) {
    console.error('Error creating employee:', error);
    res.status(500).json({ error: 'Failed to create employee' });
  }
});

// Update employee
router.put('/:id', certAuthMiddleware, async (req, res) => {
  const { name, email, role, hourly_rate, is_active } = req.body;

  try {
    const result = await pool.query(
      `UPDATE employees
       SET name = COALESCE($1, name),
           email = COALESCE($2, email),
           role = COALESCE($3, role),
           hourly_rate = COALESCE($4, hourly_rate),
           is_active = COALESCE($5, is_active),
           updated_at = CURRENT_TIMESTAMP
       WHERE id = $6
       RETURNING id, name, email, role, hourly_rate, is_active, updated_at`,
      [name, email, role, hourly_rate, is_active, req.params.id]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Employee not found' });
    }

    res.json(result.rows[0]);
  } catch (error) {
    console.error('Error updating employee:', error);
    res.status(500).json({ error: 'Failed to update employee' });
  }
});

// Get employee by current user (cert)
router.get('/current/profile', certAuthMiddleware, (req, res) => {
  if (!req.user) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  res.json({
    id: req.user.id,
    name: req.user.name,
    email: req.user.email,
    role: req.user.role,
    certificate: req.user.cert,
  });
});

export default router;
