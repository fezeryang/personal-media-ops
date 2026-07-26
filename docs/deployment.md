# Backend and crawler worker deployment

The target layout is:

```text
/opt/personal-media-ops
/opt/personal-media-ops/backend
/opt/personal-media-ops/frontend/dist
/opt/mediacrawler
/var/lib/mediaops
/var/log/mediaops
```

MediaCrawler remains an external installation. Do not copy it into this
repository or modify its official source.

## Prepare directories

Run these once with administrative privileges:

```bash
sudo install -d -o mediaops -g mediaops /var/lib/mediaops
sudo install -d -o mediaops -g mediaops /var/lib/mediaops/crawler-output/tasks
sudo install -d -o mediaops -g mediaops /var/lib/mediaops/qrcodes
sudo install -d -o mediaops -g mediaops /var/log/mediaops/crawler
```

The `mediaops` user needs read/execute access to
`/opt/mediacrawler/.venv/bin/python` and
`/var/lib/mediaops/bin/run_mediacrawler.py`.

## Install backend dependencies

```bash
cd /opt/personal-media-ops/backend
uv sync --frozen
```

Copy `.env.example` to `.env`, keep it owned by the deployment user, and do not
commit it.

Required production values:

```dotenv
MEDIAOPS_DATABASE_PATH=/var/lib/mediaops/mediaops.db
MEDIACRAWLER_PYTHON=/opt/mediacrawler/.venv/bin/python
MEDIACRAWLER_RUNNER=/var/lib/mediaops/bin/run_mediacrawler.py
MEDIAOPS_OUTPUT_ROOT=/var/lib/mediaops/crawler-output
MEDIAOPS_LOG_ROOT=/var/log/mediaops
MEDIAOPS_QRCODE_ROOT=/var/lib/mediaops/qrcodes
MEDIAOPS_NODE_BINARY=/usr/bin/node
CRAWLER_POLL_INTERVAL_SECONDS=1
```

Use `MEDIAOPS_NODE_BIN_DIR` instead of `MEDIAOPS_NODE_BINARY` when only the
directory is known. The worker constructs a child `PATH` explicitly, so
PyExecJS does not rely on an interactive shell profile.

## Database initialization

No manual migration command is required for this phase. API or worker startup
creates the database parent directory and applies idempotent
`CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` statements.

To verify:

```bash
sudo -u mediaops /opt/personal-media-ops/backend/.venv/bin/python \
  -c "from app.core.config import settings; from app.repositories.crawler_tasks import CrawlerTaskRepository; CrawlerTaskRepository(settings.database_path).initialize()"
```

Back up `/var/lib/mediaops/mediaops.db` before future schema migrations.

## Build the frontend

The production frontend uses same-origin `/api` requests. Do not put the
server IP or `127.0.0.1` in a production build:

```bash
cd /opt/personal-media-ops/frontend
npm ci
npm run lint
npm run test
npm run build
```

The static output is `/opt/personal-media-ops/frontend/dist`. The optional
`VITE_API_BASE_URL` variable is a Vite build-time value. Leave it empty for the
recommended same-origin deployment.

For local development, `npm run dev` starts Vite on `127.0.0.1:5173` and
proxies `/api` to `http://127.0.0.1:8000`.

## Runner contract

The worker launches the configured Python and runner using an argument array,
never a shell. The service-owned runner must support:

```text
--platform bili
--crawler-type search
--keywords <text>
--login-type qrcode
--requested-count <1..20>
--output-dir <generated task directory>
--qrcode-path <generated PNG path>
--max-concurrency-num 1
--enable-comments false
--enable-sub-comments false
```

The caller cannot override these flags or paths.

## systemd

Install the examples and reload systemd:

```bash
sudo cp deploy/systemd/mediaops-api.service.example \
  /etc/systemd/system/mediaops-api.service
sudo cp deploy/systemd/mediaops-crawler-worker.service.example \
  /etc/systemd/system/mediaops-crawler-worker.service
sudo systemctl daemon-reload
sudo systemctl enable --now mediaops-api mediaops-crawler-worker
```

Check status and logs:

```bash
systemctl status mediaops-api mediaops-crawler-worker
journalctl -u mediaops-crawler-worker -f
```

Only one worker should be enabled. A second worker exits because it cannot
acquire the database-derived lock file. On restart, stale `running` or
`waiting_login` tasks are marked `failed` with an interruption message.

## Nginx and BaoTa

Create an Nginx site for the public hostname and set its document root to:

```text
/opt/personal-media-ops/frontend/dist
```

The site needs SPA fallback and a same-origin API proxy. A minimal server
configuration is:

```nginx
server {
    listen 80;
    server_name your-domain.example;
    root /opt/personal-media-ops/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

In BaoTa, create a static website with the same document root, then add the
`location /api/` reverse-proxy block in the site's Nginx configuration. Keep
the `location /` SPA fallback. Do not use BaoTa's static-directory proxy as a
replacement for the `/api/` upstream.

After changing Nginx configuration:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

With same-origin deployment, CORS is not involved in normal browser requests.
If a separate development origin is intentionally used, add that exact origin
to backend `FRONTEND_ORIGINS`; never use a wildcard in production.

## Update an existing server

Run as the deployment user unless a command explicitly uses `sudo`:

```bash
cd /opt/personal-media-ops
git pull --ff-only origin main

cd /opt/personal-media-ops/backend
uv sync --frozen
uv run pytest

cd /opt/personal-media-ops/frontend
npm ci
npm run build

sudo systemctl restart mediaops-api mediaops-crawler-worker
sudo nginx -t
sudo systemctl reload nginx
```

Verify the same-origin API and frontend:

```bash
curl -fsS http://127.0.0.1:8000/api/health
curl -I https://your-domain.example/
curl -fsS https://your-domain.example/api/health
```
