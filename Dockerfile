FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir poetry
COPY backend/pyproject.toml backend/poetry.lock* ./
RUN poetry install --no-dev

COPY backend/app ./app
COPY --from=frontend-builder /app/frontend/dist ./static

ENV PYTHONUNBUFFERED=1
ENV VITE_API_URL=/api

EXPOSE 8000
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
