import express from 'express';
import https from 'https';
import fs from 'fs';
import path from 'path';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';
import session from 'express-session';
import passport from 'passport';
import { Pool } from 'pg';
import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

// Import routes and middleware
import { certAuthMiddleware } from './middleware/cert-auth';
import { auditLog } from './middleware/audit-log';
import employeesRouter from './routes/employees';
import payrollRouter from './routes/payroll';
import tipsRouter from './routes/tips';
import transactionsRouter from './routes/transactions';
import dashboardRouter from './routes/dashboard';
import auditRouter from './routes/audit';
import cakeWebhookRouter from './routes/cake-webhook';

const app = express();
const PORT = process.env.PORT || 8443;

// Database connection
export const pool = new Pool({
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD,
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT || '5432'),
  database: process.env.DB_NAME || 'bams_dashboard',
});

// Middleware
app.use(helmet());
app.use(morgan('combined'));
app.use(cors({
  origin: process.env.CORS_ORIGIN || 'http://localhost:3000',
  credentials: true,
}));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Session configuration
app.use(session({
  secret: process.env.SESSION_SECRET || 'your-secret-key-change-in-production',
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: process.env.NODE_ENV === 'production',
    httpOnly: true,
    maxAge: 24 * 60 * 60 * 1000, // 24 hours
  },
}));

// Passport initialization
app.use(passport.initialize());
app.use(passport.session());

// Certificate authentication middleware
app.use(certAuthMiddleware);

// Audit logging
app.use(auditLog);

// Routes
app.use('/api/employees', employeesRouter);
app.use('/api/payroll', payrollRouter);
app.use('/api/tips', tipsRouter);
app.use('/api/transactions', transactionsRouter);
app.use('/api/dashboard', dashboardRouter);
app.use('/api/audit', auditRouter);
app.use('/webhook/cake', cakeWebhookRouter);

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    environment: process.env.NODE_ENV,
  });
});

// Root endpoint
app.get('/', (req, res) => {
  res.json({
    name: 'BAMs Dashboard API',
    version: '2.0.0',
    status: 'running',
    authenticated: !!req.user,
    endpoints: {
      employees: '/api/employees',
      payroll: '/api/payroll',
      tips: '/api/tips',
      transactions: '/api/transactions',
      dashboard: '/api/dashboard',
      audit: '/api/audit',
      webhook: '/webhook/cake',
    },
  });
});

// Error handling middleware
app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
  console.error('Error:', err);
  res.status(err.status || 500).json({
    error: err.message || 'Internal Server Error',
    status: err.status || 500,
  });
});

// Setup HTTPS with client certificate requirement
const options = {
  key: fs.readFileSync(path.join(__dirname, '../certs/server.key')),
  cert: fs.readFileSync(path.join(__dirname, '../certs/server.crt')),
  ca: fs.readFileSync(path.join(__dirname, '../certs/ca.crt')),
  requestCert: true,
  rejectUnauthorized: false, // Let middleware handle rejection
};

https
  .createServer(options, app)
  .listen(PORT, () => {
    console.log(`
╔════════════════════════════════════════════╗
║       BAMs Dashboard Server                ║
║       Secure mTLS Authentication            ║
╚════════════════════════════════════════════╝

🔒 Server running on https://localhost:${PORT}
📊 API endpoints available
🔐 Client certificate authentication enabled
⚠️  Requires valid client certificate to access

Database: ${process.env.DB_NAME || 'bams_dashboard'}
Environment: ${process.env.NODE_ENV || 'development'}

Ready for secure connections! 🚀
    `);
  });

export default app;
