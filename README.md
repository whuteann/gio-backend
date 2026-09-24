# gio-backend

FastAPI + PostgreSQL backend for Gio, run via Docker Compose.

## Stack

- **API**: FastAPI (Uvicorn, `--reload` in dev)
- **DB**: PostgreSQL 15 (`postgres:15-alpine`)
- **ORM / migrations**: SQLAlchemy + Alembic
- **Auth** (planned, not yet wired): JWT via `python-jose` + `bcrypt`

## Ports

Several other local projects on this machine already occupy the "default"
ports (5432, 5433, and even 8000), so `gio-backend` uses these instead:

| Service | Container port | Host port | URL |
|---|---|---|---|
| `app` (FastAPI) | 8000 | **8010** | http://localhost:8010 |
| `db` (Postgres) | 5432 | **5434** | `localhost:5434` (e.g. for a GUI client) |

If 8010/5434 ever collide with something else, change the left-hand side of
the `ports:` mapping in `docker-compose.yaml` (e.g. `"8020:8000"`) — nothing
else needs to change, since `app` always talks to `db` over the internal
Docker network as `db:5432`, never through the host port mapping.

## First-time setup

```bash
cp .env.example .env    # only if .env doesn't already exist
docker compose up -d --build
```

Then confirm it's alive:

```bash
curl http://localhost:8010/health
# {"status":"ok","database":"connected"}
```

## Everyday commands

All run from the `gio-backend/` directory.

| Task | Command |
|---|---|
| Start (build if needed) | `docker compose up -d --build` |
| Start (no rebuild) | `docker compose up -d` |
| Stop (keep data) | `docker compose stop` |
| Stop and remove containers/network (keep data volume) | `docker compose down` |
| Stop and **wipe the database too** | `docker compose down -v` |
| Restart just the API (e.g. after changing `requirements.txt`) | `docker compose up -d --build app` |
| Tail API logs | `docker compose logs -f app` |
| Tail DB logs | `docker compose logs -f db` |
| Container status | `docker compose ps` |
| Shell into the API container | `docker compose exec app bash` |
| psql shell into the DB | `docker compose exec db psql -U gio -d gio` |

Code changes under `app/` are picked up automatically — the container runs
`uvicorn --reload` and the project directory is bind-mounted, so you don't
need to rebuild for a plain code edit. You only need `--build` when
`requirements.txt` or the `Dockerfile` changes.

## Database migrations (Alembic)

Alembic is wired to `app.config.settings.database_url` and
`app.database.Base.metadata` (see `alembic/env.py`), so it always targets the
same database the app itself uses — no separate config to keep in sync.

Run these from inside the `app` container so the Python environment and
`DATABASE_URL` match what the app sees:

| Task | Command |
|---|---|
| Create a migration from model changes (autogenerate) | `docker compose exec app alembic revision --autogenerate -m "describe the change"` |
| Apply all pending migrations | `docker compose exec app alembic upgrade head` |
| Roll back one migration | `docker compose exec app alembic downgrade -1` |
| Show current DB revision | `docker compose exec app alembic current` |
| Show migration history | `docker compose exec app alembic history` |

The initial schema (users, auth, personality, check-ins, Inner Readings,
recommendations, gamification, journal — see `docs/dev_log_0001.md`) is
already migrated in (`alembic/versions/9a3e05e4b10a_initial_schema.py`).
Autogenerate a new migration any time the models under `app/models/` change.

## Seeding

Not implemented yet — there's no `app/seed` module or seed data yet. Once one
exists, the command to run it will be documented here (the planned shape is a
one-off `docker compose exec app python -m app.seed.run`-style invocation,
matching the sibling backends' convention, but that's not real yet — don't
run it).

## Environment variables

Set in `.env` (gitignored; `.env.example` is the tracked template):

| Variable | Used by | Purpose |
|---|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | `db` service only | Postgres container init |
| `DATABASE_URL` | `app` | SQLAlchemy connection string, e.g. `postgresql+psycopg2://gio:gio@db:5432/gio` |
| `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | `app` | JWT signing (see `docs/dev_log_0001.md` for what's actually wired to it) |
| `CORS_ORIGINS` | `app` | Comma-separated browser origins allowed to call the API — `gio-member-app`'s dev server (`http://localhost:3000`) by default |

`app/config.py` reads these via `pydantic-settings` and deliberately ignores
unknown keys (`extra="ignore"`) since `.env` also carries the `POSTGRES_*`
vars that only `docker-compose.yaml` needs for variable substitution — those
aren't Settings fields and shouldn't be.

## Troubleshooting

- **`port is already allocated` on `docker compose up`**: another project on
  this machine is holding that host port. Check with
  `lsof -iTCP -sTCP:LISTEN -P | grep <port>`, then change the host side of
  the mapping in `docker-compose.yaml`.
- **`/health` returns `{"status":"error","database":"unreachable"}`**: the
  `app` container is up but can't reach Postgres — check
  `docker compose logs db` and `docker compose ps` (the `db` health check
  must show `healthy`).
