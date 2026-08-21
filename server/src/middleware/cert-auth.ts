import { Request, Response, NextFunction } from 'express';

// Extend Express Request type to include certificate info
declare global {
  namespace Express {
    interface Request {
      user?: {
        id: string;
        name: string;
        email: string;
        role: string;
        cert: string;
      };
    }
  }
}

/**
 * Client Certificate Authentication Middleware
 * Verifies that the request comes from an authorized device certificate
 */
export const certAuthMiddleware = (req: Request, res: Response, next: NextFunction) => {
  // Skip auth for health check and root
  if (req.path === '/health' || req.path === '/') {
    return next();
  }

  const cert = req.socket.getPeerCertificate?.();

  if (!cert || Object.keys(cert).length === 0) {
    return res.status(401).json({
      error: 'Client certificate required',
      message: 'This endpoint requires mutual TLS (mTLS) authentication',
    });
  }

  // Extract certificate information
  const subject = cert.subject;
  const certFingerprint = req.socket.getPeerCertificate?.()?.fingerprint;

  // Verify certificate is valid
  if (cert.valid_from) {
    const validFrom = new Date(cert.valid_from);
    const validTo = new Date(cert.valid_to);
    const now = new Date();

    if (now < validFrom || now > validTo) {
      return res.status(401).json({
        error: 'Certificate expired or not yet valid',
        validFrom: cert.valid_from,
        validTo: cert.valid_to,
      });
    }
  }

  // In production, you would:
  // 1. Verify cert against CA certificate
  // 2. Check cert fingerprint against approved list in database
  // 3. Map cert to user/device
  // For now, we accept any valid cert from the CA

  // Extract user info from certificate subject
  // Format: CN=user_id, O=BAMs, OU=device_id
  const commonName = subject?.CN || 'unknown';
  const orgUnit = subject?.OU || 'unknown';
  const org = subject?.O || 'BAMs';

  req.user = {
    id: commonName,
    name: commonName.replace(/_/g, ' '),
    email: `${commonName}@bams.local`,
    role: 'staff',
    cert: certFingerprint || 'unknown',
  };

  // Log cert usage for audit trail
  console.log(`[CERT AUTH] User: ${commonName}, Device: ${orgUnit}, Fingerprint: ${certFingerprint}`);

  next();
};

/**
 * Require specific role middleware
 */
export const requireRole = (roles: string[]) => {
  return (req: Request, res: Response, next: NextFunction) => {
    if (!req.user) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    if (!roles.includes(req.user.role)) {
      return res.status(403).json({
        error: 'Forbidden',
        message: `Required roles: ${roles.join(', ')}`
      });
    }

    next();
  };
};

/**
 * Optional authentication - passes if authenticated, continues if not
 */
export const optionalAuth = (req: Request, res: Response, next: NextFunction) => {
  // Try to get cert info, but don't fail if not present
  const cert = req.socket.getPeerCertificate?.();

  if (cert && Object.keys(cert).length > 0) {
    const subject = cert.subject;
    const commonName = subject?.CN || 'anonymous';
    req.user = {
      id: commonName,
      name: commonName.replace(/_/g, ' '),
      email: `${commonName}@bams.local`,
      role: 'staff',
      cert: req.socket.getPeerCertificate?.()?.fingerprint || 'unknown',
    };
  }

  next();
};
