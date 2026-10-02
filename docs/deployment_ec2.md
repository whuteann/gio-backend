# Deploying gio-backend on a shared EC2 instance

The correct procedure, distilled from actually doing it once (2026-10-02)
against `i-0805258d6f2600150` ("bracelet-api-backend", Amazon Linux 2023,
`ap-southeast-5`). That box is **not** a blank instance — it already runs
several other apps behind one shared Nginx (`chat.`, `api.`, `admin.`,
`chatdev.giobyquartzic.com`), which caused most of the real friction below.
Read the "Gotchas" section before touching a shared box like this again.

## Prerequisites

- An EC2 instance reachable via AWS Session Manager (or SSH), with the repo
  already cloned.
- An IAM user with console/SSM access, if you don't already have a terminal
  open on the box.

## 1. Install Docker + the plugins Amazon Linux 2023 doesn't ship by default

AL2023's `docker` package includes neither `compose` nor `buildx` — both
need to be added separately, or `docker compose up --build` fails outright.

```bash
sudo dnf update -y
sudo dnf install -y docker
sudo systemctl enable --now docker

# Compose v2 plugin
mkdir -p /root/.docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /root/.docker/cli-plugins/docker-compose
chmod +x /root/.docker/cli-plugins/docker-compose

# buildx plugin — compose v2's `--build` requires buildx >= 0.17
BUILDX_VERSION=$(curl -s https://api.github.com/repos/docker/buildx/releases/latest | grep '"tag_name":' | cut -d '"' -f4)
curl -SL "https://github.com/docker/buildx/releases/download/${BUILDX_VERSION}/buildx-${BUILDX_VERSION}.linux-amd64" \
  -o /root/.docker/cli-plugins/docker-buildx
chmod +x /root/.docker/cli-plugins/docker-buildx

docker --version && docker compose version && docker buildx version
```

## 2. Recreate `.env`

`.env` is gitignored, so a fresh clone never has it. Recreate it with the
same shape as local dev — two things matter more here than locally:

- **`CORS_ORIGINS`** must be the exact origin(s) that will call this API —
  scheme + host, **no trailing slash, no path**. Browsers send the `Origin`
  header with no trailing slash; FastAPI's `CORSMiddleware` does an exact
  string match. `https://your-frontend.vercel.app/` (trailing slash) will
  never match `https://your-frontend.vercel.app` and every request will be
  silently rejected with no useful error beyond "CORS error" in the browser.
- `DATABASE_URL` stays pointed at the `db` **service name** (`db:5432`),
  never the host's own IP — Compose's internal network resolves that name
  to the right container regardless of which host this runs on.

## 3. Pick a free host port before bringing it up

On a shared box, don't assume the port in `docker-compose.yaml` is free.
Check first:
```bash
docker ps -a
sudo ss -tlnp | grep ':8010\|:8011'   # whatever port you're about to use
```
If it's taken (by a leftover container *or* an unrelated process already
on the box), change the host side of the mapping in `docker-compose.yaml`
(`"8011:8000"` instead of `"8010:8000"`, etc.) rather than fighting for the
original port.

## 4. Bring it up and migrate

```bash
docker compose up -d --build
docker compose exec app alembic upgrade head
docker compose logs app --tail 30   # confirm "Application startup complete."
```

Sanity-check from the box itself before touching DNS/Nginx at all:
```bash
curl http://localhost:<port>/health
```

## 5. Decide how it'll be reached publicly

Two real options, in order of preference:

- **A real subdomain you control** (e.g. `gio-api.giobyquartzic.com`) — add
  an A record pointing at the instance's IP, then Certbot against that name.
- **No domain available**: use `<public-ip>.sslip.io` — a free service that
  resolves automatically to that IP, which lets Certbot issue a real
  Let's Encrypt cert with zero DNS setup. Good enough for a demo; a real
  subdomain is better for anything longer-lived.

Either way, **HTTPS is not optional** if a browser-based frontend calls
this — browsers hard-block any `fetch`/`XHR` from an `https://` page to a
plain `http://` target (mixed content), with no setting to bypass it. This
only doesn't matter for server-to-server callers (curl, another backend),
which can use plain `http://<ip>:<port>` right now, no TLS needed.

## 6. Before creating any new Nginx config — check for a conflicting one

**This is the step that actually cost the most time.** On a box that
already runs other sites, there may already be a server block for the
exact hostname you're about to use — from an earlier attempt, or from
initial box setup, possibly months old and forgotten. Always check first:
```bash
sudo grep -rln "<your-hostname>" /etc/nginx/conf.d/
```
If that returns a file, **edit the existing block** — don't create a new
one. Nginx resolves `server_name` by exact match across the *entire*
config regardless of which file it's in; a duplicate `server_name` in a
new file is silently ignored (`nginx -t` only warns, it doesn't fail), and
whatever the pre-existing block does keeps winning. This is exactly what
happened here: an old block for `<ip>.sslip.io` already existed in
`/etc/nginx/conf.d/final.conf`, proxying to port `8000` (a different app
entirely) — a brand-new `gio-backend-sslip.conf` with the same
`server_name` got created successfully, passed `nginx -t`, reloaded fine,
and did precisely nothing, because the old block in `final.conf` kept
serving every request.

If no file matches, create a dedicated block and get a cert for it:
```bash
sudo tee /etc/nginx/conf.d/<name>.conf << 'EOF'
server {
    listen 80;
    server_name <your-hostname>;
    location / {
        proxy_pass http://127.0.0.1:<port>;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d <your-hostname>
```

If editing an existing block instead, change only its `proxy_pass` line to
the right port — don't touch anything else in a shared config file.
Back it up first (`sudo cp final.conf final.conf.bak`) since one file can
hold multiple unrelated sites' config.

## 7. Verify through the real path, not a shortcut

Test the actual public hostname over HTTPS — not a direct `curl` to the
container's host port, which bypasses Nginx entirely and tells you nothing
about whether the public path works:
```bash
curl -i https://<your-hostname>/health
```
Expect `200` with `content-type: application/json` and a real JSON body.
A `400`/`404`/unexpected body here (even with a seemingly-valid TLS
handshake) means Nginx is routing the request somewhere other than your
app — go back to step 6.

Also worth checking directly when anything's ambiguous:
```bash
sudo tail -f /var/log/nginx/error.log /var/log/nginx/access.log
```
then fire the request once — the access log line (status code + response
byte count) is ground truth for what actually happened, faster than
inferring it from browser DevTools.

## 8. Point the frontend at it

```
NEXT_PUBLIC_API_BASE_URL=https://<your-hostname>/api/v1
```
Note the required `/api/v1` suffix — this app's frontend client expects
the base URL to already include it (see `gio-member-app/lib/api/client.ts`).
`NEXT_PUBLIC_*` vars are baked in at build time on Vercel — changing the
value alone does nothing until the next build runs; trigger a redeploy.

## 9. If it still looks broken after all of the above

- **Browsers cache a failed CORS preflight** for `Access-Control-Max-Age`
  seconds (600s/10min by default here). If you just fixed `CORS_ORIGINS`
  and retested within that window, you may be looking at a cached failure,
  not a live one. Test in an Incognito window, or wait out the cache.
- `CORS_ORIGINS` (and anything else in `docker-compose.yaml`'s
  `environment:` block) is baked into the container at **creation**, not
  read live — `docker compose restart` is not enough after an `.env`
  change; it needs `docker compose up -d` to actually recreate the
  container with the new value. Confirm what the running container
  actually has, don't assume:
  ```bash
  docker compose exec app python -c "from app.config import settings; print(settings.cors_origin_list)"
  ```
