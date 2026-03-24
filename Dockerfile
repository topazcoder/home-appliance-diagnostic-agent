FROM python:3.12-slim

WORKDIR /app

# postgresql-client provides pg_isready (used by entrypoint.sh)
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency installation
RUN pip install --no-cache-dir uv

# Copy full source
COPY . .

# Install all project dependencies from pyproject.toml into .venv
RUN uv sync --no-dev

RUN chmod +x /app/entrypoint.sh

# Make the venv's binaries available system-wide
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "app.api.httpserver:app", "--host", "0.0.0.0", "--port", "8000"]
