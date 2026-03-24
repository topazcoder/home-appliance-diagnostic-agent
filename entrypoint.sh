#!/bin/bash
set -e

echo "Waiting for Postgres..."
until pg_isready -h db -U "$POSTGRES_USER"; do
  sleep 1
done

echo "Applying migrations..."
/app/.venv/bin/alembic upgrade heads

echo "Seeding database..."
/app/.venv/bin/python -m scripts.seed

echo "Starting server..."
exec /app/.venv/bin/uvicorn app.api.httpserver:app --host 0.0.0.0 --port 8000
