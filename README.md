# Real-Time Satellite Tracking & Conjunction Analysis



Live satellite position tracking (SGP4 orbital propagation) and close-approach
detection between orbiting objects (KD-tree spatial screening), over the
public CelesTrak TLE catalog — with user accounts, saved satellites, email
alerts, historical conjunction reports, and a 3D mission-control dashboard.

**Three components, three different skills, one system:**
- `backend/` — Python (FastAPI): the orbital-mechanics engine, REST API, database, auth, alerts
- `java-scheduler/` — Java (Quartz): reliably triggers a TLE refresh on a cron schedule
- `frontend/` — HTML/CSS/JS (Three.js): the live dashboard, served by the backend

---

## 1. Quick start (local, no Docker)

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # then open .env and fill in your own values — see section 3
uvicorn app.main:app --reload
```

Then open:
- **Dashboard:** http://localhost:8000/
- **Swagger / interactive API docs:** http://localhost:8000/docs
- **Health check:** http://localhost:8000/api/health

Run the tests:
```bash
cd backend
pytest -v
```

The first time the server starts, it downloads the live TLE catalog from
CelesTrak automatically. After that, TLEs only refresh when
`/api/admin/refresh-tles` is called — either manually (see below) or by the
Java scheduler running on its cron.

### Manually triggering a refresh (without the Java scheduler running)
```bash
curl -X POST http://localhost:8000/api/admin/refresh-tles \
  -H "X-Admin-Key: <the ADMIN_API_KEY value from your .env>"
```

---

## 2. Quick start (Docker — recommended for the "real deployment" story)

```bash
cp backend/.env.example backend/.env    # fill in your own values first
docker compose up --build
```

Same URLs as above: dashboard at http://localhost:8000/, docs at
http://localhost:8000/docs.

### Running the Java scheduler alongside it
```bash
cd java-scheduler
# edit src/main/resources/config.properties first — see section 3
mvn clean package
java -jar target/tle-scheduler-1.0.0.jar
```
It will call `/api/admin/refresh-tles` every 15 minutes by default (the cron
schedule is set in `config.properties`).

---

## 3. Where to put YOUR credentials

There are exactly two config files you need to edit — nothing else in the
project should need to change to get it running.

### `backend/.env` (copy from `backend/.env.example`)
| Setting | What it's for |
|---|---|
| `DATABASE_URL` | Where user accounts, saved satellites, and conjunction history are stored. Defaults to a local SQLite file — no setup needed. Swap for a Postgres URL for a real deployment. |
| `JWT_SECRET_KEY` | Signs login tokens. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_API_KEY` | Shared secret so only the Java scheduler (not the public internet) can trigger a TLE refresh. Must match `java-scheduler/.../config.properties` exactly. |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | Your email account, for sending conjunction alerts. Leave `SMTP_HOST` blank to disable email (alerts still show on the dashboard either way). For Gmail: host `smtp.gmail.com`, port `587`, and the password must be a 16-character **App Password** from https://myaccount.google.com/apppasswords — not your normal Gmail password. |

### `java-scheduler/src/main/resources/config.properties`
| Setting | What it's for |
|---|---|
| `api.url` | The backend's refresh endpoint. `http://localhost:8000/...` locally, or your deployed URL in production. |
| `api.adminKey` | Must be identical to `ADMIN_API_KEY` in `backend/.env`. |
| `scheduler.cronExpression` | How often to refresh (Quartz cron syntax). Default: every 15 minutes. |

---

## 4. Database — what's actually stored, and where

**SQLite by default** — a single file, `backend/satellite_platform.db`, created
automatically on first run. Nothing to install. Good for development and for
a live demo.

Three tables (defined in `backend/app/models.py`):
- `users` — accounts (username, email, **bcrypt-hashed** password — never plaintext)
- `saved_satellites` — which satellites each user is tracking, and whether they want email alerts for it
- `conjunction_events` — a permanent log of every close approach ever detected — this is what the "historical reports" feature reads from

**Live satellite positions are never stored** — they're recalculated from the
in-memory TLE catalog on every request, because a stored position would be
stale within seconds.

To move to Postgres for a real deployment: install `psycopg2-binary`, and set
`DATABASE_URL=postgresql+psycopg2://<user>:<password>@<host>:5432/<db_name>`
in `.env`. No code changes needed — SQLAlchemy handles the difference.

---

## 5. File-by-file guide

### `backend/app/`
| File | What it does |
|---|---|
| `main.py` | App entrypoint. Creates DB tables, loads the initial TLE catalog, wires up all routers, serves the dashboard. |
| `config.py` | Every setting, read from `.env`. The one place secrets flow in from. |
| `database.py` | SQLAlchemy engine/session setup. |
| `models.py` | The 3 database tables (User, SavedSatellite, ConjunctionEvent). |
| `schemas.py` | Request/response shapes — also what generates the Swagger docs. |
| `auth.py` | Password hashing, JWT creation/verification, the "who is this request from" logic. |
| `alerts.py` | Sends the close-approach email via SMTP. |
| `orbital/tle_store.py` | Downloads and holds the live TLE catalog in memory. |
| `orbital/propagator.py` | The SGP4 wrapper — live position, pass prediction, and raw 3D snapshots for conjunction screening. |
| `orbital/conjunction.py` | The KD-tree close-approach screening engine — the algorithmic core of the project. |
| `routers/auth_router.py` | `/api/auth/register`, `/api/auth/login` |
| `routers/satellites_router.py` | Satellite list, live position, pass prediction, saved satellites (CRUD) |
| `routers/conjunctions_router.py` | Live screening results + historical log |
| `routers/admin_router.py` | The protected endpoint the Java scheduler calls on its cron |

### `backend/tests/`
| File | What it does |
|---|---|
| `test_conjunction.py` | Pure unit tests for the KD-tree screening math — no network or DB needed. |
| `test_api.py` | Integration tests through the real FastAPI app (auth flow, satellite endpoints), using a fake in-memory ISS TLE so it works offline / in CI. |

### `java-scheduler/src/main/java/com/satellite/scheduler/`
| File | What it does |
|---|---|
| `SchedulerApp.java` | Entry point — registers the job + cron trigger, starts Quartz. |
| `TleRefreshJob.java` | The actual job: calls the backend's refresh endpoint over HTTP. |
| `AppConfig.java` | Loads `config.properties` into a typed object. |

### `frontend/`
| File | What it does |
|---|---|
| `index.html` | Dashboard page structure. |
| `css/style.css` | The mission-control design system — colors, type, layout. |
| `js/globe.js` | The 3D wireframe globe renderer (Three.js) — the visual centerpiece. |
| `js/app.js` | Talks to the API, manages login state, drives the globe and side panels. |

### Root
| File | What it does |
|---|---|
| `docker-compose.yml` | Builds and runs the backend (which also serves the frontend) in one container. |
| `backend/Dockerfile` | The container image definition. **Must be built from the project root** (`docker build -f backend/Dockerfile .`) so it can copy both `backend/` and `frontend/` — `docker compose` already does this correctly. |
| `.github/workflows/ci.yml` | On every push: installs deps, runs pytest, builds the Docker image. |

---

## 6. Why these specific technical choices

- **SGP4 via `skyfield`** instead of raw math: `skyfield` wraps the same
  industry-standard SGP4 implementation used across the space industry, and
  also gives clean subpoint (lat/lon) and pass-prediction calculations for
  free, instead of hand-rolling coordinate transforms.
- **KD-tree (`scipy.spatial.cKDTree`)** instead of comparing every satellite
  pair: `query_pairs()` finds every close pair across the whole catalog in
  one spatial query, which is what makes conjunction screening viable at
  catalog scale instead of an O(n²) crawl.
- **TLEs live in memory, not the database**: they're only valid for a few
  hours anyway, so persisting them would add complexity for zero benefit.
  Only the things that need to persist — accounts, saved satellites,
  conjunction history — touch the database.
- **The Java component does exactly one job** (reliable scheduled HTTP
  trigger) rather than duplicating orbital-mechanics logic in two languages —
  that's a deliberate, defensible architecture decision worth stating
  explicitly in an interview.
