#!/bin/bash

echo "📦 Building Business-EOS..."

# Build frontend
echo "🎨 Building frontend..."
cd frontend
npm install
npm run build
cd ..

# Copy frontend dist to backend static
echo "📂 Copying frontend build to backend..."
rm -rf static
mkdir -p static
cp -r frontend/dist/* static/

echo "✅ Build complete!"
echo ""
echo "📋 Next steps:"
echo "1. Set up .env file with required variables"
echo "2. Run: uvicorn app.main:app --reload"
echo "3. Visit: http://localhost:8000"
