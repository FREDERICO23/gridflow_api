FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for asyncpg / psycopg builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

EXPOSE 8000

RUN chmod +x start.sh

# Default: run migrations then start the API server.
# Override CMD in docker-compose for the worker service.
CMD ["./start.sh"]
