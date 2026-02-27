# GridFlow API

Energy Load Platform — ingests raw energy consumption files and produces an 8,760-hour annual load forecast vector with confidence intervals.

---

## Table of Content

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Local Development](#local-development)
- [Running the API](#running-the-api)
- [Frontend](#frontend)
- [Running Tests](#running-tests)
- [API Reference](#api-reference)
- [Environment Variables](#environment-variables)
- [Deployment](#deployment)

---

## Architecture

| Layer | Technology |
| --- | --- |
| API | FastAPI (async) + Uvicorn |
| Database | PostgreSQL 16 + TimescaleDB |
| ORM | SQLAlchemy 2.x (async) + asyncpg |
| Migrations | Alembic |
| Task queue | Celery + Redis |
| Object storage | Google Cloud Storage |
| Forecasting | Prophet + NumPy / Pandas |
| Runtime | Python 3.11, Docker |

### Services (docker-compose)

```text
api      → FastAPI on :8000
worker   → Celery worker (concurrency 4)
db       → TimescaleDB on :5432
redis    → Redis 7 on :6379
```

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) ≥ 24 + Docker Compose v2
- Python 3.11 *(only needed to run tests outside Docker)*
- A Google Cloud project with a GCS bucket *(optional for Phase 1)*

---

## Local Development

### 1. Clone and configure

```bash
git clone https://github.com/FREDERICO23/gridflow_api.git
cd gridflow_api

cp .env.example .env
```

Open `.env` and set at minimum:

```dotenv
API_KEY=your-secret-api-key-here
```

All other values default to the Docker Compose service names and are ready to use as-is.

### 2. (Optional) GCS credentials

If you need GCS during development, place your service account JSON at:

```text
credentials/gcs-service-account.json
```

Then uncomment in `.env`:

```dotenv
GCS_CREDENTIALS_PATH=/app/credentials/gcs-service-account.json
```

Leave it commented to skip GCS — the API starts normally and reports `not_configured` for storage.

### 3. Start all services

```bash
docker compose up --build
```

First boot pulls images and installs dependencies (~2 min). On subsequent starts:

```bash
docker compose up
```

Services are healthy when you see:

```text
api     | INFO:     Application startup complete.
worker  | ready.
```

### 4. Run database migrations

In a separate terminal (while services are running):

```bash
docker compose exec api alembic upgrade head
```

### 5. Verify

```bash
# Liveness — no auth required
curl http://localhost:8000/health

# Service status — requires API key
curl http://localhost:8000/api/v1/status \
  -H "X-API-Key: your-secret-api-key-here"
```

Interactive API docs: <http://localhost:8000/docs>

### Useful commands

```bash
# Tail logs for a specific service
docker compose logs -f api
docker compose logs -f worker

# Open a Python shell inside the api container
docker compose exec api python

# Create a new Alembic migration after model changes
docker compose exec api alembic revision --autogenerate -m "describe change"

# Stop everything (keeps volumes)
docker compose down

# Stop and wipe the database volume
docker compose down -v
```

---

## Running the API

### With Docker Compose (recommended)

```bash
# Start all services (API, Celery worker, TimescaleDB, Redis)
docker compose up --build

# Run in the background
docker compose up -d --build

# Apply database migrations (run once after first start)
docker compose exec api alembic upgrade head

# Stop all services
docker compose down
```

The API is available at <http://localhost:8000>.

### API only (no worker / DB)

If you already have PostgreSQL and Redis running externally, you can start just the FastAPI server:

```bash
# Set connection variables in your environment or .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Celery worker only

```bash
celery -A app.workers.celery_app worker --loglevel=info --concurrency=4
```

---

## Frontend

The frontend is a React + TypeScript + Vite app located in the [`frontend/`](frontend/) directory.

### API key in the navbar

When you open the app, the header has an **API key** field. Enter the same value you set as `API_KEY` in your `.env` file:

```dotenv
# .env (project root)
API_KEY=dev-api-key   ← type this exact value into the navbar field
```

The default out-of-the-box value is `dev-api-key`. The key is saved in `localStorage` so you only need to enter it once per browser. The frontend sends it as an `X-API-Key` header on every request to the API.

### Install dependencies

```bash
cd frontend
npm install
```

### Run the dev server

```bash
npm run dev
```

Vite starts on <http://localhost:5173> with hot module replacement.

### Other commands

```bash
# Type-check and build for production
npm run build

# Preview the production build locally
npm run preview

# Lint
npm run lint
```

---

## Running Tests

Tests run against the actual app without a live database (Phase 1). Install dev dependencies locally:

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

With coverage:

```bash
pytest tests/ --cov=app --cov-report=term-missing
```

Lint:

```bash
ruff check app/ tests/
```

---

## API Reference

All endpoints live under `/api/v1/` and require an `X-API-Key` header, **except** `/health`.

### Authentication

Pass your API key in every request header:

```text
X-API-Key: <your-key>
```

Missing or wrong key returns `401 Unauthorized`.

### Endpoints

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/health` | — | Liveness probe |
| `GET` | `/api/v1/status` | ✓ | Service status, DB + storage connectivity |
| `POST` | `/api/v1/upload` | ✓ | Upload a load-profile file, start processing job |
| `GET` | `/api/v1/upload/{job_id}/status` | ✓ | Poll job processing status |
| `GET` | `/api/v1/jobs/{job_id}/parsed` | ✓ | Parsed time-series data |
| `GET` | `/api/v1/jobs/{job_id}/normalized` | ✓ | Normalised time-series |
| `GET` | `/api/v1/jobs/{job_id}/enrichment` | ✓ | Weather enrichment data |
| `GET` | `/api/v1/jobs/{job_id}/quality-report` | ✓ | Data quality report |
| `GET` | `/api/v1/jobs/{job_id}/forecast` | ✓ | 8,760-hour forecast vector (JSON) |
| `GET` | `/api/v1/jobs/{job_id}/forecast/download` | ✓ | Forecast vector (CSV download) |

Job status flow:

```text
queued → parsing → normalizing → enriching → quality_check → forecasting → complete
                                                                         ↘ failed
```

### Example: upload a file

```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -H "X-API-Key: your-secret-api-key-here" \
  -F "file=@/path/to/load_profile.csv" \
  -F "forecast_year=2026"
```

### Example: poll job status

```bash
curl http://localhost:8000/api/v1/upload/<job_id>/status \
  -H "X-API-Key: your-secret-api-key-here"
```

### Example: download forecast

```bash
curl http://localhost:8000/api/v1/jobs/<job_id>/forecast/download \
  -H "X-API-Key: your-secret-api-key-here" \
  -o forecast.csv
```

Full schema available at `/docs` (Swagger UI) or `/redoc`.

---

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `API_KEY` | `dev-api-key` | Secret key for `X-API-Key` header. **Change in production.** |
| `DATABASE_URL` | `postgresql+asyncpg://gridflow:gridflow@db:5432/gridflow` | Async SQLAlchemy connection URL |
| `REDIS_URL` | `redis://redis:6379/0` | Celery broker + result backend |
| `GCS_BUCKET_RAW` | `gridflow-raw-uploads` | GCS bucket for uploaded files |
| `GCS_BUCKET_OUTPUT` | `gridflow-forecast-outputs` | GCS bucket for forecast outputs |
| `GCS_CREDENTIALS_PATH` | *(unset — uses ADC)* | Path to GCS service account JSON inside container |
| `DEFAULT_TIMEZONE` | `Europe/Berlin` | Processing timezone (primary market: DE) |
| `DEFAULT_COUNTRY_CODE` | `DE` | Country code for holiday calendars |
| `WEATHER_ENRICHMENT_ENABLED` | `true` | Set `false` to skip Open-Meteo enrichment |
| `DEBUG` | `false` | Enable FastAPI debug mode |

---

## Deployment

### Environment

Use the same Docker images as local. Recommended production overrides:

```dotenv
DEBUG=false
API_KEY=<strong-random-key>
DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<host>:5432/<db>
REDIS_URL=redis://<host>:6379/0
GCS_CREDENTIALS_PATH=/app/credentials/gcs-service-account.json
```

Generate a strong API key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Build the image

```bash
docker build -t gridflow-api:latest .
```

### Run API server

```bash
docker run -d \
  --env-file .env \
  -p 8000:8000 \
  gridflow-api:latest
```

### Run Celery worker

```bash
docker run -d \
  --env-file .env \
  gridflow-api:latest \
  celery -A app.workers.celery_app worker --loglevel=info --concurrency=4
```

### Run migrations at deploy time

```bash
docker run --rm --env-file .env gridflow-api:latest \
  alembic upgrade head
```

### Reverse proxy (nginx / Caddy)

Point your proxy to `http://api:8000`. Recommended headers:

```nginx
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

### Health check endpoint

Configure your load balancer or orchestrator (Cloud Run, ECS, K8s) to probe:

```http
GET /health  →  200 {"status": "ok"}
```

No authentication required for this endpoint.

### Google Cloud Storage — ADC vs service account

| Environment | Recommended |
| --- | --- |
| GCP (Cloud Run, GCE, GKE) | Application Default Credentials (leave `GCS_CREDENTIALS_PATH` unset) |
| Outside GCP | Mount service account JSON and set `GCS_CREDENTIALS_PATH` |
