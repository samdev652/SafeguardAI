# Safeguard AI

Production-oriented full-stack foundation for Kenya's AI-powered multi-hazard early warning and anticipatory disaster response platform.

## Stack

- Frontend: Next.js 14 (App Router), React, Leaflet, mobile-first map UI
- Backend: Django 5, Django REST Framework, Simple JWT, GeoDjango
- Geospatial: PostGIS (via GeoDjango)
- Async jobs: Celery + Redis (ingestion and alert dispatch)
- AI analysis: Google Gemini 1.5 Flash API
- Alert channels: Africa's Talking (SMS), WhatsApp Cloud API

## Monorepo Structure

- `backend/`: Django API, Celery tasks, hazard analysis, rescue routing
- `frontend/`: Next.js dashboard, onboarding, map-first alert UX

## GeoDjango Setup (Cross-Platform)

GeoDjango can auto-discover GDAL on many systems. Only set `GDAL_LIBRARY_PATH` in `backend/.env` if startup fails with a GDAL error. Do not copy Linux paths to other OSes.

- Linux (Ubuntu/Debian):
	- Install: `sudo apt-get install -y gdal-bin libgdal-dev postgis`
	- Typical path: `GDAL_LIBRARY_PATH=/lib/x86_64-linux-gnu/libgdal.so`
- macOS (Homebrew):
	- Install: `brew install gdal postgis`
	- Typical path on Apple Silicon: `GDAL_LIBRARY_PATH=/opt/homebrew/lib/libgdal.dylib`
	- Typical path on Intel: `GDAL_LIBRARY_PATH=/usr/local/lib/libgdal.dylib`
- Windows:
	- Install GDAL through OSGeo4W or conda-forge
	- Set `GDAL_LIBRARY_PATH` to the GDAL DLL path, e.g. `C:\\OSGeo4W\\bin\\gdalXXX.dll`

If your app starts without GDAL errors, leave `GDAL_LIBRARY_PATH` unset.

PostgreSQL/PostGIS minimum setup:

- Create DB user and DB:
	- `CREATE USER safeguard_user WITH PASSWORD 'your_password';`
	- `CREATE DATABASE safeguard_ai OWNER safeguard_user;`
- Enable PostGIS in the DB:
	- `\c safeguard_ai`
	- `CREATE EXTENSION IF NOT EXISTS postgis;`

## Quick Start (Local)

1. Copy env values:
- `cp backend/.env.example backend/.env`
- `cp frontend/.env.example frontend/.env.local`

2. Start services:
- `docker compose up --build`

3. Initialize demo data:
- `docker compose exec backend python manage.py createsuperuser`
- `docker compose exec backend python manage.py seed_demo_data`
- `docker compose exec backend python manage.py load_ward_boundaries --file /app/data/kenya_wards_sample.geojson`

4. Open apps:
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Django Admin: `http://localhost:8000/admin`

## Core API Endpoints

- `POST /api/citizens/register/`: citizen onboarding payload
- `GET /api/hazards/risks/`: latest risk assessments
- `GET /api/hazards/risks/ward-heatmap/`: GeoJSON ward boundaries with latest risk metadata
- `GET /api/hazards/risks/events/`: SSE event stream for live risk updates
- `GET /api/rescue/units/nearest/?latitude=-1.28&longitude=36.81`: nearest 3 units via PostGIS `ST_Distance`
- `POST /api/rescue/sos/dispatch/`: authenticated SOS dispatch
- `GET /api/alerts/my/`: authenticated citizen alerts

## Throughput and 500+ Concurrent Users

Recommended baseline configuration:

- Django app pods/instances: 2-3 (each `gunicorn --workers 4 --threads 4`)
- Celery workers: 2 nodes, concurrency 4-8 each
- Postgres with connection pooling (PgBouncer recommended)
- Redis single small instance (upgrade when queues grow)
- CDN and edge caching for static frontend assets
- Polling/SSE update interval: 60s to balance freshness and load

For production:

- Deploy frontend on Vercel, backend on Railway
- Use Supabase Postgres + PostGIS
- Use Redis Cloud for broker/backing queues
- Enable Sentry DSNs for both frontend and backend
- Add rate limits and API auth hardening at ingress

## AI and Data Flow

1. Celery Beat triggers `ingest_hazard_data_task` every 30 minutes.
2. Task fetches KMD + NOAA feeds.
3. Each normalized observation is analyzed by Gemini (`gemini-1.5-flash`).
4. Resulted risk assessments are saved and alert dispatch tasks queued.
5. SMS/WhatsApp dispatch runs asynchronously.
6. Frontend consumes risks through REST and live SSE stream.

## Accessibility

- High contrast color system for low-visibility/outdoor use
- Large risk states for sub-1-second visual recognition
- Web Speech API support for audible critical alerts
- Mobile-first controls with large tap targets, including double-confirm SOS

## Authentication

- Frontend session auth via NextAuth credentials provider
- Token exchange handled server-side by NextAuth against Django Simple JWT
- Protected SOS dispatch consumes session access token (`session.accessToken`)

## Testing

- Backend API + task tests:
	- `docker compose exec backend python manage.py test apps.hazards apps.rescue`
- Frontend mobile E2E tests:
	- `cd frontend && npx playwright install --with-deps`
	- `cd frontend && npm run test:e2e`

## Security Notes

- Keep all secrets in env files and cloud secret stores
- Do not expose backend DB directly to frontend
- Use HTTPS-only cookies/tokens in production
- Rotate API keys regularly
