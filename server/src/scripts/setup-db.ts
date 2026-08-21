import { Pool } from 'pg';
import fs from 'fs';
import path from 'path';
import dotenv from 'dotenv';

dotenv.config();

const pool = new Pool({
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD,
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT || '5432'),
  database: process.env.DB_NAME || 'bams_dashboard',
});

async function setupDatabase() {
  console.log(`
╔════════════════════════════════════════╗
║  BAMs Dashboard Database Setup         ║
╚════════════════════════════════════════╝
`);

  try {
    // Read SQL schema
    const sqlPath = path.join(__dirname, '../config/database.sql');
    const sql = fs.readFileSync(sqlPath, 'utf-8');

    console.log('📝 Executing database schema...');
    await pool.query(sql);

    console.log('✅ Database schema created successfully!');
    console.log(`
📊 Tables created:
  - employees
  - employee_shifts
  - transactions
  - daily_closings
  - tips
  - tips_split
  - payroll
  - employee_tabs
  - employee_tab_transactions
  - payments
  - audit_log
  - budget_targets

📈 Views created:
  - employee_total_owed

🎯 Ready to use!
    `);
  } catch (error) {
    console.error('❌ Database setup failed:', error);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

setupDatabase();
