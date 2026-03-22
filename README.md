# Safeguard AI

Production-oriented full-stack foundation for Kenya's AI-powered multi-hazard early warning and anticipatory disaster response platform.

## Recent Changes

- Public trust surfaces added: `/`, `/register`, `/threats`, `/threats/[id]`, `/how-it-works`, `/download`
- Public OTP-first phone subscription flow (no password required)
- Public threat share links with metadata-friendly detail pages
- County officials role-protected portal under `/county/*`
- New county analytics, alert history export, incident management, and dispatch log APIs
- Public coverage analytics endpoint for map choropleth
- Faster local frontend rebuilds using Turbopack (`npm run dev`)

## Stack

- Frontend: Next.js 14 (App Router), React, Leaflet, Framer Motion, Recharts
- Backend: Django 5, Django REST Framework, Simple JWT, GeoDjango
- Geospatial: PostGIS (via GeoDjango)
- Async jobs: Celery + Redis
- AI analysis: Google Gemini 1.5 Flash API
- Alert channels: Africa's Talking (SMS), WhatsApp Cloud API

## Monorepo Structure

- `backend/`: Django API, Celery tasks, hazard analysis, rescue routing
- `frontend/`: Next.js public pages, dashboards, map UX, auth

## Route Map (Frontend)

- `/`: public landing page with live threat highlights
- `/register`: public 3-step alert registration (location -> channels -> OTP)
- `/threats`: public full live feed (map + filters + share)
- `/threats/[id]`: public threat detail page with share metadata
- `/how-it-works`: public trust/education page with process + FAQ + coverage
- `/download`: app download/waitlist page
- `/dashboard`: authenticated user dashboard
- `/county/overview` and `/county/*`: county officials portal (role protected)

## Page Tour

- Landing (`/`): Public trust entry point with live threat highlights, map preview, and quick actions.
- Register (`/register`): Fast 3-step signup for alert channels using OTP phone verification.
- Threats (`/threats`): Public nationwide live feed with map, filters, sorting, and share actions.
- Threat Detail (`/threats/[id]`): Share-friendly threat card with metadata-rich preview content.
- How It Works (`/how-it-works`): Plain-language explainer for citizens, county officials, and NGO partners.
- County Portal (`/county/*`): Role-protected operations center for county disaster management teams.
- Dashboard (`/dashboard`): Authenticated live operational view for ongoing monitoring and action.

## Screenshots

Current visual assets available in-repo:

| Flow | Preview |
|---|---|
| Location step illustration | ![Location Step](frontend/public/illustrations/location.svg) |
| Channel selection illustration | ![Channel Step](frontend/public/illustrations/channels.svg) |
| Phone verification illustration | ![Phone Step](frontend/public/illustrations/phone.svg) |

To add real product screenshots, place files under `docs/screenshots/` and reference them in this section, for example:

- `docs/screenshots/landing.png`
- `docs/screenshots/register.png`
- `docs/screenshots/threats.png`
- `docs/screenshots/county-overview.png`

## GeoDjango Setup (Cross-Platform)

GeoDjango can auto-discover GDAL on many systems. Only set `GDAL_LIBRARY_PATH` in `backend/.env` if startup fails with a GDAL error.

Linux (Ubuntu/Debian):
- Install: `sudo apt-get install -y gdal-bin libgdal-dev postgis`
- Typical path: `GDAL_LIBRARY_PATH=/lib/x86_64-linux-gnu/libgdal.so`

macOS (Homebrew):
- Install: `brew install gdal postgis`
- Apple Silicon path: `GDAL_LIBRARY_PATH=/opt/homebrew/lib/libgdal.dylib`
- Intel path: `GDAL_LIBRARY_PATH=/usr/local/lib/libgdal.dylib`

Windows:
- Install GDAL via OSGeo4W or conda-forge
- Set `GDAL_LIBRARY_PATH` to your GDAL DLL path, e.g. `C:\OSGeo4W\bin\gdalXXX.dll`

If your app starts without GDAL errors, leave `GDAL_LIBRARY_PATH` unset.

### PostgreSQL / PostGIS minimum setup

- `CREATE USER safeguard_user WITH PASSWORD 'your_password';`
- `CREATE DATABASE safeguard_ai OWNER safeguard_user;`
- Connect to DB: `\c safeguard_ai`
- `CREATE EXTENSION IF NOT EXISTS postgis;`

## Quick Start

### Docker

1. Copy env files:
- `cp backend/.env.example backend/.env`
- `cp frontend/.env.example frontend/.env.local`

2. Start services:
- `docker compose up --build`

3. Seed data:
- `docker compose exec backend python manage.py createsuperuser`
- `docker compose exec backend python manage.py seed_demo_data`
- `docker compose exec backend python manage.py load_ward_boundaries --file /app/data/kenya_wards_sample.geojson`

4. Open:
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Django Admin: `http://localhost:8000/admin`

### Native local (no Docker)

Backend:
1. `cd backend`
2. `./venv/bin/python -m pip install -r requirements.txt`
3. `./venv/bin/python manage.py migrate`
4. `./venv/bin/python manage.py runserver 0.0.0.0:8000`

Frontend:
1. `cd frontend`
2. `npm install`
3. `npm run dev`

Notes:
- Prefer running backend commands from `backend/` with `./venv/bin/python ...`
- If GeoDjango fails to boot, set `GDAL_LIBRARY_PATH` in `backend/.env`
- Ensure `NEXTAUTH_BACKEND_URL` points to backend (typically `http://localhost:8000`)

## Core API Endpoints

### Public trust endpoints

- `GET /api/risk/current/` (optional `?ward=`)
- `GET /api/risk/count/`
- `GET /api/stats/public/`
- `GET /api/stats/coverage/`
- `GET /api/locations/search/?q=`
- `GET /api/hazards/risks/ward-heatmap/`

### Public registration endpoints

- `POST /api/alerts/otp/send/`
- `POST /api/alerts/otp/verify/`
- `POST /api/alerts/subscribe/`

`POST /api/alerts/otp/send/` accepts:
- `phone`: Kenya number, e.g. `+2547XXXXXXXX`
- `channel`: `sms` or `whatsapp` (default `sms`)

### Operational endpoints

- `GET /api/rescue/units/nearest/?latitude=-1.28&longitude=36.81`
- `POST /api/rescue/sos/dispatch/`
- `GET /api/alerts/my/`
- `POST /api/alerts/sms/reply/webhook/` (Africa's Talking inbound SMS callback)

### County officials endpoints

- `GET /api/county/overview/`
- `PATCH /api/risk/{id}/acknowledge/`
- `GET /api/alerts/history/`
- `GET /api/alerts/export/?county={county}&format=csv`
- `GET /api/citizens/county-users/`
- `GET /api/alerts/incidents/`
- `PATCH /api/alerts/incidents/{id}/`
- `GET /api/alerts/dispatch-log/`

## Authentication and Access

- NextAuth credentials provider on frontend
- Django Simple JWT token exchange on backend
- Authenticated route: `/dashboard/*` requires login
- Authenticated route: `/county/*` requires login with `role === 'county_official'`
- NextAuth auth fetches use request timeouts for faster failure when backend is down

## Throughput Guidance (500+ Concurrent Users)

- Django app instances: 2-3 (`gunicorn --workers 4 --threads 4`)
- Celery workers: 2 nodes, concurrency 4-8
- Postgres with connection pooling (PgBouncer recommended)
- Redis instance sized by queue load
- CDN + edge cache for static frontend assets
- 60s polling/SSE intervals to balance freshness and load

## AI and Data Flow

1. Celery Beat triggers ingestion.
2. KMD + NOAA feeds are normalized, with Open-Meteo fallback for Kenya coverage.
3. Gemini analyzes each observation.
4. Risk assessments are persisted.
5. Alert dispatch jobs are queued.
6. Frontend consumes REST + live updates.

## Testing

Backend:
- `docker compose exec backend python manage.py test apps.hazards apps.rescue`
- `docker compose exec backend python manage.py test apps.alerts apps.hazards`

Frontend:
- `cd frontend && npx playwright install --with-deps`
- `cd frontend && npm run test:e2e`

Note: if your DB role lacks `CREATEDB`, Django test DB creation can fail.

## Security Notes

- Keep secrets in env files and secret managers
- Do not expose database directly to frontend
- Use HTTPS-only token/cookie handling in production
- Rotate API keys regularly

## Free-Tier OTP Setup (Student Friendly)

Use this setup for zero-cost local development with real phone delivery.

Backend `.env` minimum:

```env
AFRICASTALKING_USERNAME=sandbox
AFRICASTALKING_API_KEY=your_africas_talking_sandbox_key
AFRICASTALKING_SENDER_ID=

WHATSAPP_TOKEN=your_meta_permanent_or_long_lived_token
WHATSAPP_PHONE_NUMBER_ID=your_whatsapp_test_number_id

OTP_ALLOW_DEV_FALLBACK=false
DEBUG=False
```

Africa's Talking sandbox notes:
- Keep `AFRICASTALKING_USERNAME=sandbox`.
- Use sandbox API key from Africa's Talking dashboard.
- OTP SMS uses `POST /api/alerts/otp/send/` with `channel: sms`.

WhatsApp Cloud API free-tier notes:
- Use Meta test number in the same app as your token.
- Recipient phone must join the sandbox/test flow from Meta dashboard first.
- OTP on WhatsApp uses `POST /api/alerts/otp/send/` with `channel: whatsapp`.

Behavior implemented:
- OTP is accepted only when provider confirms send.
- OTP expires after 5 minutes.
- Phone must verify OTP before subscription.
- Alert dispatch sends emergency guidance and nearest rescue contacts over selected channels (`sms`, `whatsapp`, `push`).

## Community Verification by SMS Reply

When a risk assessment is `high` or `critical`, the backend now sends a second ward-wide SMS prompt after the main alert:

- Prompt text asks citizens to reply `YES` (disaster visible) or `NO` (normal conditions).
- `3` YES replies mark the assessment as community verified and trigger a ward-wide confirmation SMS.
- `5` NO replies downgrade the assessment to safe, mark all-clear, and trigger a ward-wide all-clear SMS.

Webhook endpoint used by Africa's Talking:

- `POST /api/alerts/sms/reply/webhook/`

Dashboard setup (Africa's Talking):

1. Open your SMS product in the Africa's Talking dashboard.
2. Set callback URL to your public backend URL plus `/api/alerts/sms/reply/webhook/`.
3. Example production callback URL: `https://api.your-domain.com/api/alerts/sms/reply/webhook/`
4. Save and test by sending an SMS reply containing `YES` or `NO`.

Note: localhost callbacks are not reachable by Africa's Talking. Use a public HTTPS URL (for example via your cloud deployment or an HTTPS tunnel) when testing inbound replies.
