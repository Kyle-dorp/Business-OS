import { Request, Response, NextFunction } from 'express';
import { pool } from '../index';
import { v4 as uuidv4 } from 'uuid';

/**
 * Audit logging middleware
 * Logs all API requests for security and compliance
 */
export const auditLog = async (req: Request, res: Response, next: NextFunction) => {
  const startTime = Date.now();
  const requestId = uuidv4();

  // Capture response
  const originalSend = res.send;

  res.send = function (data: any) {
    const duration = Date.now() - startTime;
    const statusCode = res.statusCode;

    // Log to database (async, don't block response)
    logAuditEntry({
      requestId,
      method: req.method,
      path: req.path,
      statusCode,
      duration,
      userId: req.user?.id,
      ipAddress: req.ip,
      userAgent: req.get('user-agent'),
      cert: req.user?.cert,
    }).catch(err => console.error('Audit log error:', err));

    return originalSend.call(this, data);
  };

  next();
};

interface AuditEntry {
  requestId: string;
  method: string;
  path: string;
  statusCode: number;
  duration: number;
  userId?: string;
  ipAddress?: string;
  userAgent?: string;
  cert?: string;
}

async function logAuditEntry(entry: AuditEntry) {
  try {
    await pool.query(
      `INSERT INTO audit_log (id, action, table_name, user_id, changes, ip_address, timestamp)
       VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)`,
      [
        entry.requestId,
        `${entry.method} ${entry.path}`,
        'api_request',
        entry.userId,
        JSON.stringify({
          statusCode: entry.statusCode,
          duration: entry.duration,
          userAgent: entry.userAgent,
          cert: entry.cert,
        }),
        entry.ipAddress,
      ]
    );
  } catch (error) {
    console.error('Failed to log audit entry:', error);
  }
}
