import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';

/**
 * Certificate Generation Script
 * Creates CA, server, and client certificates for mTLS
 *
 * Usage: npm run gen:certs
 */

const certsDir = path.join(__dirname, '../certs');

// Ensure certs directory exists
if (!fs.existsSync(certsDir)) {
  fs.mkdirSync(certsDir, { recursive: true });
}

console.log(`
╔════════════════════════════════════════════╗
║   BAMs Dashboard mTLS Certificate Generator ║
╚════════════════════════════════════════════╝

Creating certificates in: ${certsDir}
`);

// Step 1: Generate CA private key
console.log('📝 Generating CA private key...');
execSync(
  `openssl genrsa -out ${path.join(certsDir, 'ca.key')} 2048`,
  { stdio: 'inherit' }
);

// Step 2: Generate CA certificate
console.log('🔐 Generating CA certificate...');
execSync(
  `openssl req -new -x509 -days 3650 -key ${path.join(certsDir, 'ca.key')} -out ${path.join(certsDir, 'ca.crt')} -subj "/C=US/ST=State/L=City/O=BAMs/CN=BAMs-CA"`,
  { stdio: 'inherit' }
);

// Step 3: Generate server private key
console.log('📝 Generating server private key...');
execSync(
  `openssl genrsa -out ${path.join(certsDir, 'server.key')} 2048`,
  { stdio: 'inherit' }
);

// Step 4: Generate server CSR
console.log('🔓 Generating server certificate signing request...');
execSync(
  `openssl req -new -key ${path.join(certsDir, 'server.key')} -out ${path.join(certsDir, 'server.csr')} -subj "/C=US/ST=State/L=City/O=BAMs/CN=localhost"`,
  { stdio: 'inherit' }
);

// Step 5: Sign server certificate with CA
console.log('✅ Signing server certificate...');
execSync(
  `openssl x509 -req -in ${path.join(certsDir, 'server.csr')} -CA ${path.join(certsDir, 'ca.crt')} -CAkey ${path.join(certsDir, 'ca.key')} -CAcreateserial -out ${path.join(certsDir, 'server.crt')} -days 365 -sha256`,
  { stdio: 'inherit' }
);

// Step 6: Create client certificate template
const clientTemplate = `
#!/bin/bash
# Generate Client Certificate for BAMs Dashboard

CLIENT_NAME=\${1:-"user1"}
DEVICE_ID=\${2:-"device1"}
CERTS_DIR=\${3:-"./certs"}

echo "🔐 Generating certificate for: \$CLIENT_NAME (\$DEVICE_ID)"

# Generate private key
openssl genrsa -out "\$CERTS_DIR/\$CLIENT_NAME-\$DEVICE_ID.key" 2048

# Generate CSR
openssl req -new -key "\$CERTS_DIR/\$CLIENT_NAME-\$DEVICE_ID.key" \\
  -out "\$CERTS_DIR/\$CLIENT_NAME-\$DEVICE_ID.csr" \\
  -subj "/C=US/ST=State/L=City/O=BAMs/OU=\$DEVICE_ID/CN=\$CLIENT_NAME"

# Sign with CA
openssl x509 -req -in "\$CERTS_DIR/\$CLIENT_NAME-\$DEVICE_ID.csr" \\
  -CA "\$CERTS_DIR/ca.crt" \\
  -CAkey "\$CERTS_DIR/ca.key" \\
  -CAcreateserial -out "\$CERTS_DIR/\$CLIENT_NAME-\$DEVICE_ID.crt" \\
  -days 365 -sha256

# Create PKCS12 bundle for easy import
openssl pkcs12 -export -out "\$CERTS_DIR/\$CLIENT_NAME-\$DEVICE_ID.p12" \\
  -inkey "\$CERTS_DIR/\$CLIENT_NAME-\$DEVICE_ID.key" \\
  -in "\$CERTS_DIR/\$CLIENT_NAME-\$DEVICE_ID.crt" \\
  -certfile "\$CERTS_DIR/ca.crt" \\
  -password pass:

echo "✅ Certificate created!"
echo "📁 Files:"
echo "   - Private key: \$CERTS_DIR/\$CLIENT_NAME-\$DEVICE_ID.key"
echo "   - Certificate: \$CERTS_DIR/\$CLIENT_NAME-\$DEVICE_ID.crt"
echo "   - PKCS12 bundle: \$CERTS_DIR/\$CLIENT_NAME-\$DEVICE_ID.p12"
`;

fs.writeFileSync(
  path.join(certsDir, 'create-client-cert.sh'),
  clientTemplate,
  { mode: 0o755 }
);

console.log(`
✅ Certificate Generation Complete!

📁 Created certificates in: ${certsDir}

Files:
  - ca.key              (CA private key)
  - ca.crt              (CA certificate)
  - ca.srl              (CA serial)
  - server.key          (Server private key)
  - server.crt          (Server certificate)
  - server.csr          (Server CSR - safe to delete)
  - create-client-cert.sh (Script to create client certs)

🎯 Next Steps:

1. Generate client certificates for each user/device:
   $ bash certs/create-client-cert.sh username device_id

   Examples:
   $ bash certs/create-client-cert.sh kyle phone
   $ bash certs/create-client-cert.sh kyle laptop
   $ bash certs/create-client-cert.sh manager phone

2. This creates:
   - username-device_id.key (private key)
   - username-device_id.crt (certificate)
   - username-device_id.p12 (for easy import)

3. Distribute .p12 files to users for import on their devices
   - On MacOS/iOS: email the .p12 file, then install from Mail
   - On Windows: double-click to install in certificate store
   - On Linux: import using cert manager or openssl

4. Users can then access the dashboard at:
   https://your-domain.com (mTLS automatically used)

⚠️  IMPORTANT:
  - Keep ca.key safe! Don't share with anyone.
  - Keep server.key safe! Don't commit to git.
  - .p12 files are for distribution but still keep secure.
  - Set strong passwords on .p12 files for distribution.

🔒 Security Notes:
  - Certificates expire after 365 days (configurable)
  - Each device has a unique certificate
  - Revocation can be done by removing certificate from trust store
  - Use in production with proper certificate management
`);
