-- BAMs Dashboard Database Schema
-- PostgreSQL

-- Employees Table
CREATE TABLE IF NOT EXISTS employees (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255) UNIQUE,
  role VARCHAR(50) NOT NULL, -- 'manager', 'staff'
  hourly_rate DECIMAL(10, 2) NOT NULL DEFAULT 0,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Employee Clock In/Out
CREATE TABLE IF NOT EXISTS employee_shifts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id UUID NOT NULL REFERENCES employees(id),
  clock_in TIMESTAMP NOT NULL,
  clock_out TIMESTAMP,
  hours DECIMAL(5, 2) GENERATED ALWAYS AS (
    EXTRACT(EPOCH FROM (clock_out - clock_in)) / 3600
  ) STORED,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Transactions (All sales/activity)
CREATE TABLE IF NOT EXISTS transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  date DATE NOT NULL,
  type VARCHAR(50) NOT NULL, -- 'sale', 'discount', 'refund', 'void', 'payment'
  amount DECIMAL(10, 2) NOT NULL,
  payment_method VARCHAR(50), -- 'cash', 'card', 'check', 'tab'
  employee_id UUID REFERENCES employees(id),
  description TEXT,
  source VARCHAR(50), -- 'cake_pos', 'manual', 'import'
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_date (date),
  INDEX idx_employee (employee_id)
);

-- Daily Closing Data (from CAKE)
CREATE TABLE IF NOT EXISTS daily_closings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  date DATE NOT NULL UNIQUE,
  total_sales DECIMAL(10, 2),
  cash_in DECIMAL(10, 2),
  card_in DECIMAL(10, 2),
  discounts DECIMAL(10, 2),
  refunds DECIMAL(10, 2),
  voids DECIMAL(10, 2),
  cash_out DECIMAL(10, 2),
  variance DECIMAL(10, 2),
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tips Tracking
CREATE TABLE IF NOT EXISTS tips (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  date DATE NOT NULL,
  total_tips DECIMAL(10, 2) NOT NULL,
  note TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tips Split (how tips are divided among employees)
CREATE TABLE IF NOT EXISTS tips_split (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tip_id UUID NOT NULL REFERENCES tips(id),
  employee_id UUID NOT NULL REFERENCES employees(id),
  amount DECIMAL(10, 2) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Payroll Tracking
CREATE TABLE IF NOT EXISTS payroll (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id UUID NOT NULL REFERENCES employees(id),
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  hours DECIMAL(7, 2) DEFAULT 0,
  base_pay DECIMAL(10, 2) DEFAULT 0,
  tips DECIMAL(10, 2) DEFAULT 0,
  employee_tabs_reduction DECIMAL(10, 2) DEFAULT 0,
  taxes_withheld DECIMAL(10, 2) DEFAULT 0,
  total_owed DECIMAL(10, 2) DEFAULT 0,
  status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'paid', 'partial'
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Employee Tabs (Employee Debt)
CREATE TABLE IF NOT EXISTS employee_tabs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id UUID NOT NULL REFERENCES employees(id),
  amount DECIMAL(10, 2) NOT NULL DEFAULT 0,
  description TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Employee Tab Transactions (log of tab purchases)
CREATE TABLE IF NOT EXISTS employee_tab_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id UUID NOT NULL REFERENCES employees(id),
  amount DECIMAL(10, 2) NOT NULL,
  type VARCHAR(20) NOT NULL, -- 'purchase', 'reduction', 'payment'
  description TEXT,
  reference_id UUID, -- link to payment or tab
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Payments Log (track all payroll payments)
CREATE TABLE IF NOT EXISTS payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id UUID NOT NULL REFERENCES employees(id),
  payroll_id UUID REFERENCES payroll(id),
  amount DECIMAL(10, 2) NOT NULL,
  payment_date DATE NOT NULL,
  payment_method VARCHAR(50), -- 'cash', 'check', 'direct_deposit'
  reference_number VARCHAR(255),
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit Log (track all changes)
CREATE TABLE IF NOT EXISTS audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  action VARCHAR(100) NOT NULL,
  table_name VARCHAR(50),
  record_id UUID,
  user_id UUID,
  changes JSONB,
  ip_address VARCHAR(45),
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_timestamp (timestamp)
);

-- Budget Targets
CREATE TABLE IF NOT EXISTS budget_targets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  date DATE NOT NULL UNIQUE,
  daily_target DECIMAL(10, 2) NOT NULL DEFAULT 5000,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for common queries
CREATE INDEX idx_employee_active ON employees(is_active);
CREATE INDEX idx_transaction_date ON transactions(date);
CREATE INDEX idx_payroll_employee ON payroll(employee_id);
CREATE INDEX idx_payroll_period ON payroll(period_start, period_end);
CREATE INDEX idx_tips_date ON tips(date);
CREATE INDEX idx_audit_action ON audit_log(action);

-- Create views for common queries
CREATE OR REPLACE VIEW employee_total_owed AS
SELECT
  e.id,
  e.name,
  COALESCE(SUM(et.amount), 0) as total_tabs_owed,
  COALESCE(SUM(p.total_owed - COALESCE(pay.paid, 0)), 0) as payroll_owed
FROM employees e
LEFT JOIN employee_tab_transactions et ON e.id = et.employee_id
LEFT JOIN payroll p ON e.id = p.employee_id
LEFT JOIN (
  SELECT employee_id, SUM(amount) as paid
  FROM payments
  GROUP BY employee_id
) pay ON e.id = pay.employee_id
GROUP BY e.id, e.name;

-- Insert default daily budget
INSERT INTO budget_targets (date, daily_target)
VALUES (CURRENT_DATE, 5000)
ON CONFLICT (date) DO NOTHING;
