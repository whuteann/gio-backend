So you# gio-backend — production deployment runbook

How `gio-backend` is actually deployed and operated on the shared EC2 box, and
the exact procedure for each kind of change. Every fact below was confirmed by
running commands on the live host on **2026-10-16** (see §10 for the commands) —
nothing here is inferred from repo files, which for this service are misleading
in two specific ways (§2).

Companions:
- [deployment_ec2.md](deployment_ec2.md) — the **first-time** bootstrap (installing
  Docker/buildx on AL2023, creating the nginx block, certbot). Read that only when
  standing up a *new* box; for an existing deploy, this file supersedes it.
- [EC2_PRODUCTION_INFRASTRUCTURE.md](../../../EC2_PRODUCTION_INFRASTRUCTURE.md) — the
  whole box, including the three other services sharing it.
- [AUREN_GIO_DEPLOYMENT_CHECKLIST.md](../../../AUREN_GIO_DEPLOYMENT_CHECKLIST.md) —
  the account-linking feature's cross-service release list.

---

## 1. The deployment profile

| | |
|---|---|
| Host | `ip-172-31-46-227.ap-southeast-5.compute.internal`, Amazon Linux 2023, x86_64 |
| Public IP | `43.217.180.202` |
| Disk / RAM | 20 GB (36% used) / **1901 MB, no swap** — see §2.4 |
| Code on box | `/opt/gio-backend` (git checkout, `root`-owned, remote `git@github.com:whuteann/gio-backend.git`, branch `main`) |
| Compose file | `/opt/gio-backend/docker-compose.yaml`, compose project name `gio-backend` |
| App container | `gio-backend-app-1`, image `gio-backend-app`, host `8011` → container `8000` |
| DB container | `gio-backend-db-1`, `postgres:15-alpine`, host `5434` → container `5432` |
| DB storage | docker volume `gio-backend_postgres_data` (local driver, ~67 MB) |
| Network | `gio-backend_gio-network` (bridge) |
| Public URL | `https://aurenapi.giobyquartzic.com` → nginx → `127.0.0.1:8011` |
| Fallback URL | `https://43.217.180.202.sslip.io` → same target |
| TLS | Let's Encrypt via certbot; `certbot-renew.timer` active and renewing |
| Restart policy | `unless-stopped`, and `docker.service` is `enabled` → **survives reboot** |
| Migrations | alembic, `current == heads == 40486e5c4908`, single head, no drift |

Not `gio-backend`, despite what local dev suggests: **port `8010` on this box is the
chatbot service.** gio-backend is `8011`. Local dev maps gio-backend to 8010, which
is a coincidence of the sandbox. Any production config pointing at 8010 silently
hits a different application.

---

## 2. Four things about this deployment that are not normal

Everything in §3–§7 follows from these. Read them before running any deploy command.

### 2.1 Production runs `--reload` against a bind-mounted checkout

```
command=[uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload]
MOUNT bind /opt/gio-backend -> /app rw=true
```

The container does not run the code baked into its image — the bind mount shadows
`/app` with the host checkout, and uvicorn's reloader watches it. Consequences:

- **A code deploy is just `git pull`.** Touching any `.py` file under
  `/opt/gio-backend` makes uvicorn restart its worker within a second or two, with
  the new code live. No rebuild, no `docker compose` command.
- **`docker compose up -d --build` does nothing for application code.** The
  image's `COPY . .` layer is invisible at runtime. A rebuild only matters when
  `requirements.txt` changes, since site-packages live in the image at
  `/usr/local/lib/python3.12/`, outside the mount.
- **The reloader is an uncontrolled deploy trigger.** Editing a file in place on
  the box — including a half-finished edit, or a `git pull` that lands partway
  through — restarts the app mid-request. There is no atomic switch-over.
- `.env` is **not** watched (the reloader only watches `*.py`), so an env change
  needs an explicit restart. See §6.

### 2.2 Environment variables arrive by two different routes

The compose `environment:` block whitelists only these ten:

`ACCESS_TOKEN_EXPIRE_MINUTES`, `ALGORITHM`, `BRACELET_BACKEND_URL`,
`CORS_ORIGINS`, `DATABASE_URL`, `INTERNAL_LINK_SECRET`, `OPENAI_API_KEY`,
`OPENAI_MODEL`, `REFRESH_TOKEN_EXPIRE_DAYS`, `SECRET_KEY`

Everything else the app reads — **all `XENDIT_*`, `PAYMENT_GATEWAY_ENABLED`, all
`LUMENART_*`** — is absent from that block, yet resolves to real values at runtime.
It reaches the app because the bind mount (§2.1) places `/opt/gio-backend/.env` at
`/app/.env`, and `app/config.py` sets `env_file=".env"` relative to `WORKDIR /app`.
pydantic-settings reads it directly.

This gives two classes of variable with **different update procedures** (§6), and
one trap: pydantic-settings ranks real environment variables *above* `.env` file
values, so for any of the ten above, the value injected at container-create time
wins over whatever `.env` currently says. Editing `.env` and restarting changes
nothing for those; the container has to be recreated.

It also means **removing the bind mount would silently disable Xendit and
LumenArt** — `payment_gateway_enabled` would fall back to its `True` default with
an empty `xendit_secret_key`, i.e. checkout attempts failing against Xendit rather
than cleanly bypassing it. Do not "harden" the compose file by dropping the mount
without first moving those vars into `environment:`.

### 2.3 `requirements.txt` has no version pins

Every dependency is unpinned (`fastapi`, `sqlalchemy`, `pydantic`, …). The running
image was built around 2026-10-01. **Any `--build` rebuild resolves against PyPI
as of that moment**, so a rebuild performed to fix one thing can pull a breaking
major version of something unrelated. Treat `--build` as a change in its own right
(§4), never as a routine step — and never as a troubleshooting reflex.

### 2.4 The box has 1.9 GB RAM, no swap, shared with four other services

`braceletBackend` (2 uvicorn workers, port 8000), `bracelet-management-backend`
(8001), and two chatbot instances (8010, 8060) all run on this host alongside both
gio containers. At the time of inspection ~400 MB was available. A `pip install`
during an image build is the heaviest thing that happens here — if a build dies
without a clear error, suspect the OOM killer, and check `dmesg | tail` before
assuming a dependency problem.

---

## 3. Routine deploy

### 3.1 Quick answer: "I just pulled — what do I run to update everything?"

**Usually nothing.** The pull *is* the deploy (§2.1) — uvicorn's reloader picks up
`.py` changes within a second or two. What else you need depends on what the pull
touched, and one command decides it:

```bash
cd /opt/gio-backend
git pull
git diff --name-only ORIG_HEAD HEAD    # <- this decides everything below
```

| If that lists… | Run |
|---|---|
| only `*.py` / templates | **nothing** — already live; just verify |
| `alembic/versions/*` | back up (§7), then `docker compose exec app alembic upgrade head` — §5 |
| `requirements.txt` | `docker compose up -d --build` — §4, and read §2.3 first |
| `docker-compose.yaml` | `docker compose up -d`, then re-check the host port is still `8011`, not the repo's `8010` |
| `.env.example` | diff against your `.env` for new vars, then §6 for which restart class they need |

Verify, always through the public hostname rather than the container port:

```bash
docker compose logs app --tail 20                   # "Application startup complete."
curl -s https://aurenapi.giobyquartzic.com/health   # {"status":"ok","database":"connected"}
```

To have it tell you instead of looking it up:

```bash
cd /opt/gio-backend && git diff --name-only ORIG_HEAD HEAD | awk '
/^alembic\/versions\// {m=1} /^requirements\.txt$/ {r=1}
/^docker-compose\.yaml$/ {c=1} /^\.env\.example$/ {e=1} {n++}
END {
 print "files changed: " n
 if (r) print "REBUILD:  docker compose up -d --build   (requirements.txt changed - unpinned, see 2.3)"
 if (c) print "RECREATE: docker compose up -d           (compose changed - verify port is 8011:8000)"
 if (m) print "MIGRATE:  pg_dump first, then docker compose exec app alembic upgrade head"
 if (e) print "ENV:      .env.example changed - diff against .env for new vars (see 6)"
 if (!r && !c && !m && !e) print "NOTHING:  code-only change, already live via --reload"
}'
```

Note `ORIG_HEAD` is set by the pull itself, so run the diff *after* pulling — and
before pulling again, or it'll describe the wrong hop.

### 3.2 Code-only change, in full

The normal case: Python changes already merged to `main` on GitHub.

```bash
cd /opt/gio-backend
git status --short            # expect: M docker-compose.yaml (see note below)
git log --oneline -1          # record this SHA — it is your rollback target
git pull
docker compose logs app --tail 20   # watch for "Application startup complete."
curl -s https://aurenapi.giobyquartzic.com/health
```

That's the whole deploy. The `git pull` writes `.py` files, uvicorn's reloader sees
them and restarts the worker itself (§2.1).

**The checkout carries one uncommitted change:** `docker-compose.yaml` is modified
on the box (the host port was changed from the repo's `8010` to `8011`, since 8010
is the chatbot here). `git pull` will refuse to proceed if an incoming commit also
touches that file. When that happens:

```bash
git stash && git pull && git stash pop   # re-apply the local port override
```
then **re-read the file** to confirm the port is still `8011:8000` before
continuing. A cleaner fix is in §9.

If the reload didn't happen (no new log lines, old behaviour persists), force it:
`docker compose restart app`.

---

## 4. Deploy that changes `requirements.txt`

This is the only case needing a rebuild, and because of §2.3 it is the riskiest
routine operation on this service.

```bash
cd /opt/gio-backend
docker image inspect gio-backend-app --format '{{.Id}}'   # save: rollback image
git pull
docker compose up -d --build
docker compose logs app --tail 40
docker compose exec app pip freeze > /root/pip-freeze-$(date +%F).txt   # record what you got
curl -s https://aurenapi.giobyquartzic.com/health
```

Before doing this, consider pinning the versions currently in production first
(`docker compose exec app pip freeze`) and committing them, so the rebuild is
reproducible rather than a lottery. Watch memory (§2.4) while the build runs.

---

## 5. Deploy that includes a migration

Alembic is clean on this service (`current == heads == 40486e5c4908`, one head) —
unlike `braceletBackend`, whose history has drifted from local. Keep it that way by
checking heads *before* upgrading, not after.

```bash
cd /opt/gio-backend
# 1. Back up first — there is no automatic backup (§7)
docker compose exec -T db pg_dump -U gio -d gio | gzip > /root/gio-$(date +%F-%H%M).sql.gz
ls -lh /root/gio-*.sql.gz

# 2. Confirm no drift before touching anything
docker compose exec app alembic current
docker compose exec app alembic heads     # must be a single head, equal to current

# 3. Pull code, then migrate explicitly — the reloader does NOT run migrations
git pull
docker compose exec app alembic upgrade head
docker compose exec app alembic current   # should now equal the new head

# 4. Verify
curl -s https://aurenapi.giobyquartzic.com/health   # checks DB connectivity too
docker compose logs app --tail 30
```

Order matters: pulling code before migrating means the reloader briefly runs new
code against the old schema. For additive migrations that's harmless; for a
destructive or renaming one, stop the app first (`docker compose stop app`),
migrate, then `docker compose start app`.

---

## 6. Changing an environment variable

Which command you need depends on which route the variable takes (§2.2).

**Class A — the ten whitelisted in `environment:`** (`SECRET_KEY`, `CORS_ORIGINS`,
`DATABASE_URL`, `INTERNAL_LINK_SECRET`, `BRACELET_BACKEND_URL`, `OPENAI_*`,
`ALGORITHM`, both token-expiry vars). The container must be **recreated**:

```bash
cd /opt/gio-backend
vi .env
docker compose up -d        # recreates the container; `restart` is NOT enough
```

A `docker compose restart app` here leaves the old value in place, because the
value was captured into the container's env at creation and takes precedence over
`.env`. This has caused real debugging sessions twice (once for `CORS_ORIGINS`,
once for a secret rotation).

**Class B — everything else** (`XENDIT_*`, `PAYMENT_GATEWAY_ENABLED`,
`LUMENART_*`). These are read from the mounted `.env` at import, so a process
restart suffices:

```bash
vi /opt/gio-backend/.env
docker compose restart app
```

**Always verify rather than assume**, for either class:

```bash
docker compose exec app python -c "
from app.config import settings as s
print(s.cors_origin_list, s.payment_gateway_enabled, s.xendit_environment, bool(s.xendit_secret_key))"
```

One browser-side caveat for `CORS_ORIGINS`: a failed preflight is cached for
`Access-Control-Max-Age` (10 min here). After fixing an origin, retest in an
Incognito window or wait the cache out, or you'll be looking at a stale failure.

---

## 7. Backups — there are none

Confirmed on the box: `crontab` is **not installed**, `/etc/cron.d/` holds nothing
relevant, and no dumps exist on disk. The entire database is one local docker
volume (`gio-backend_postgres_data`) on one EBS root volume. Whether EBS snapshots
are configured can only be checked in the AWS console — it is not visible from the
host, and should be confirmed rather than assumed.

Until that changes, treat the manual dump in §5 as mandatory before every
migration, and take one before any risky operation:

```bash
docker compose exec -T db pg_dump -U gio -d gio | gzip > /root/gio-$(date +%F-%H%M).sql.gz
```

Restore into the running container:

```bash
gunzip -c /root/gio-YYYY-MM-DD-HHMM.sql.gz | docker compose exec -T db psql -U gio -d gio
```

A nightly dump is the single highest-value improvement available here (§9).

---

## 8. Rollback

**Code** (the common case — no rebuild, no migration):

```bash
cd /opt/gio-backend
git log --oneline -5
git checkout <last-good-sha>   # reloader picks it up within seconds
docker compose logs app --tail 20
```
This leaves the checkout detached at that SHA; return to the branch later with
`git checkout main`.

**Dependencies** (after a §4 rebuild went wrong): revert `requirements.txt`, then
`docker compose up -d --build`. If the rebuild itself is what's broken and you
saved the old image ID, `docker tag <old-image-id> gio-backend-app` then
`docker compose up -d --force-recreate` without `--build`.

**Schema**: `docker compose exec app alembic downgrade -1` — only if that specific
migration has a tested `downgrade()`. Many don't. The dump from §5 is the real
rollback path for anything destructive.

---

## 9. Open items and recommended changes

Each of these is a real finding from the 2026-10-16 inspection, not a style note.

**Must fix before this is genuinely production:**

1. **`SECRET_KEY` is the placeholder `dev-secret-change-me`** — the value
   published in `.env.example` and committed to the repo. Every access and refresh
   token in production is signed with a publicly known key, so anyone can mint a
   valid token for any user. Rotate to a real generated secret (Class A
   procedure, §6 — needs `docker compose up -d`). Rotating invalidates all live
   sessions; users will have to sign in again.
2. **A live Xendit key is paired with a localhost redirect.**
   `xendit_secret_key` is `xnd_production_…`, `payment_gateway_enabled` is `True`,
   so real invoices are being created against real money — while
   `xendit_success_redirect_url` is still `http://localhost:3000/membership/payment-success`.
   That URL is passed straight to Xendit as the invoice's `success_redirect_url`
   ([subscription_payment.py:104](../app/services/subscription_payment.py#L104)),
   so a customer who pays is redirected to a dead address on their own machine.
   Set both redirect URLs to the real frontend origin (Class B, §6). Note
   `xendit_environment` says `sandbox` while the key is production — that field is
   informational only and never selects an endpoint, so the key is what's real,
   but the mismatch is worth correcting so the banner doesn't mislead.
3. **Postgres is bound to `0.0.0.0:5434`.** Whether it's actually reachable from
   the internet depends entirely on the EC2 security group, which must be checked
   in the console. Nothing on this box needs that port published — the app reaches
   the DB over the compose network as `db:5432`. Either close it in the security
   group or change the mapping to `127.0.0.1:5434:5432`.

**Worth doing:**

4. **Two nginx files mention `aurenapi.giobyquartzic.com`** —
   `/etc/nginx/conf.d/aurenapi.conf` and `/etc/nginx/conf.d/final.conf`. Duplicate
   `server_name` blocks don't fail `nginx -t`; the first match silently wins, which
   is exactly the failure mode documented in [deployment_ec2.md](deployment_ec2.md)
   §6. Confirm which block actually serves traffic and delete the loser.
   (`final.conf.bak` is not loaded — the include glob only matches `*.conf`.)
5. **`proxy_read_timeout 180s` is set on the sslip.io block but may not be on the
   `aurenapi` one.** Endpoints that call OpenAI (recommendations, inner readings)
   can exceed nginx's 60s default, which would surface as a 504 on the primary
   domain but not the fallback. Verify and match them.
6. **Move the host-port override out of the tracked compose file.** Put
   `8011:8000` in a `docker-compose.override.yaml` and add that filename to
   `.gitignore` (it is not there today), so `/opt/gio-backend` stays clean and
   `git pull` never conflicts (§3).
7. **Take `--reload` out of production.** It makes every file touch a deploy and
   adds a file watcher the box doesn't need (§2.4). Dropping it means code deploys
   become `git pull && docker compose restart app` — explicit, which is the point.
   Do not drop the bind mount at the same time without first moving the Class B
   vars into `environment:` (§2.2).
8. **Add a nightly `pg_dump`** (§7). `cronie` isn't installed; a systemd timer is
   the better fit on AL2023 anyway.
9. **Pin `requirements.txt`** from the current `pip freeze` (§2.3).
10. **Drop `http://localhost:3000` from production `CORS_ORIGINS`** — harmless in
    practice but it widens the allowlist for no production purpose.

---

## 10. Verification commands

Current state of everything in §1, re-runnable:

```bash
# What's running, where it came from, how it's wired
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker inspect gio-backend-app-1 --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}} {{.Config.Cmd}}'
docker inspect gio-backend-app-1 --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{end}}'
docker compose --project-directory /opt/gio-backend config    # the real, resolved compose file

# Which env vars come via compose vs via the mounted .env (§2.2)
docker inspect gio-backend-app-1 --format '{{range .Config.Env}}{{println .}}{{end}}'
docker compose exec app python -c "from app.config import settings as s; print(s.cors_origin_list, s.payment_gateway_enabled)"

# Deployed version, schema state
git -C /opt/gio-backend log --oneline -3 && git -C /opt/gio-backend status -sb
docker compose exec app alembic current && docker compose exec app alembic heads

# Public path — the only test that proves the real route works
curl -s https://aurenapi.giobyquartzic.com/health      # {"status":"ok","database":"connected"}
sudo nginx -T 2>/dev/null | grep -n -B2 -A6 'server_name aurenapi'
sudo certbot certificates | grep -E 'Certificate Name|Expiry'

# Logs
docker compose logs app --tail 50
sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log
```

A direct `curl http://127.0.0.1:8011/health` proves only that the container is up.
It bypasses nginx and TLS entirely, so it says nothing about whether the public
path works — always verify through the real hostname.
