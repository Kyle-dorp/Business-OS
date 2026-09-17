FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code (preserve backend/app structure for imports)
COPY backend ./backend

# Copy frontend build
COPY --from=frontend-builder /app/frontend/dist ./static

# Migrations. These were missing from the image entirely, so `alembic upgrade
# head` could never have run even if something had called it — and nothing did,
# because Railway builds from this file and ignores the startCommand in
# railway.json. The result was a production database several migrations behind,
# with sign-in returning 500 while /health stayed green.
COPY alembic.ini .
COPY migrations ./migrations

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Migrations run, but they do not gate the app.
#
# `alembic upgrade head && uvicorn` looks safer and is not: a database stamped
# at a revision this repo does not contain makes alembic exit non-zero, and the
# whole site stays down over a bookkeeping row. The column repairs in
# database.py run on boot regardless and are idempotent, so the app can bring
# its own schema up to date either way. A failure here is logged and surfaced
# at /health rather than being fatal.
CMD sh -c "alembic upgrade head || echo '[!!] alembic upgrade failed; continuing on the built-in column repairs'; uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
