# Deployment Guide

This document describes how to deploy the Telegram Bot (FastAPI) on a server.

## Requirements

- **Server**: Linux (e.g. Ubuntu 22.04), public IP or domain
- **Docker** (recommended) or Python 3.10+ with Poetry
- **PostgreSQL** 12+ (can be same host or managed DB)
- **HTTPS** for webhook (Telegram requires TLS)

## 1. Configuration

### Option A: Environment variables (recommended for server)

Create `.env` from the example (do not commit `.env`):

```bash
cp .env.example .env
# Edit .env and set at least:
#   BOT_TOKEN, DATABASE__*, WEBHOOK_URL, WEBHOOK_SECRET_TOKEN
```

When `config.json` is **not** present, the app loads from `.env` and environment variables. Use this in Docker and on servers.

### Option B: config.json (local / legacy)

If `config.json` exists in the project root, it takes precedence. See `config.json.example`.

## 2. Deploy with Docker

### Build and run (with PostgreSQL in Docker)

```bash
# Set required env (or use .env file)
export BOT_TOKEN=your_bot_token
export DATABASE__DB_NAME=telegram_bot
export DATABASE__USER=botuser
export DATABASE__PASSWORD=secure_password
export DATABASE__HOST=db
export DATABASE__PORT=5432
export DATABASE__TABLE_NAME=organizer_table
export WEBHOOK_URL=https://your-domain.com/webhook/telegram
export WEBHOOK_SECRET_TOKEN=random_secret_string
export ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

docker compose up -d
```

> **Important:** `ENCRYPTION_KEY` is required. The app will refuse to start if it is missing. Generate it once and store it securely — changing or losing the key makes all previously encrypted data in the database unreadable.

App: `http://localhost:8000`  
Health: `http://localhost:8000/webhook/health`

### Run app only (external database)

```bash
# .env must set DATABASE__HOST (and PORT if needed) to your DB host
docker compose -f docker-compose.app-only.yml up -d
# Or: docker build -t telegram-bot . && docker run --env-file .env -p 8000:8000 telegram-bot
```

## 3. Webhook setup

After the app is reachable over HTTPS:

1. Set Telegram webhook (once):

```bash
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain.com/webhook/telegram", "secret_token": "YOUR_WEBHOOK_SECRET_TOKEN"}'
```

2. Ensure `WEBHOOK_SECRET_TOKEN` in `.env` matches `secret_token` in the request (for verification).

3. Your server must expose `https://your-domain.com/webhook/telegram` and forward to the app (e.g. reverse proxy to `http://127.0.0.1:8000`).

## 4. Reverse proxy (HTTPS)

Example with **nginx** in front of the app:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate     /etc/ssl/certs/your-domain.crt;
    ssl_certificate_key  /etc/ssl/private/your-domain.key;

    location /webhook/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Telegram-Bot-Api-Secret-Token $http_x_telegram_bot_api_secret_token;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Reload nginx and ensure the app is listening on `0.0.0.0:8000` (default).

## 5. Deploy without Docker (systemd)

```bash
# Install Python 3.10+, Poetry, PostgreSQL client libs
poetry install --no-dev
# Copy .env (or config.json) into app directory
poetry run python run.py
```

Example **systemd** unit `/etc/systemd/system/telegram-bot.service`:

```ini
[Unit]
Description=Telegram Bot (FastAPI)
After=network.target postgresql.service

[Service]
Type=simple
User=appuser
WorkingDirectory=/opt/telegram-bot
EnvironmentFile=/opt/telegram-bot/.env
ExecStart=/opt/telegram-bot/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

## 6. Production checklist

- [ ] `DEBUG=false` (or unset)
- [ ] Strong `DATABASE__PASSWORD` and `WEBHOOK_SECRET_TOKEN`
- [ ] `ENCRYPTION_KEY` set and backed up securely (Fernet key — see section 2)
- [ ] `WEBHOOK_URL` and webhook set in Telegram (HTTPS only)
- [ ] Reverse proxy with valid TLS certificate
- [ ] CORS: if needed, restrict `CORS_ORIGINS` in `.env`
- [ ] Logs: ensure `logs/` is writable or use stdout (Docker logs)
- [ ] DB: backups and schema migrations applied before deploying new image (see section 9)

## 7. Health and monitoring

- **Liveness**: `GET /webhook/health` → `200` and `{"status":"ok"}`
- Docker HEALTHCHECK and systemd `Restart=always` use this endpoint.
- Optionally add Prometheus/metrics later.

## 8. Troubleshooting

- **502 Bad Gateway from nginx**: The app is not running or crashed on startup. Check `docker logs <container>` — startup failures are logged as `CRITICAL` before the process exits.
- **App exits immediately with no logs**: All logs go to `logs/log.log` inside the container by default. Run the container with a shell to read the file: `docker run --rm --env-file .env <image> sh -c "python -m uvicorn app.main:app || cat logs/log.log"`.
- **`ENCRYPTION_KEY` missing / `Field required` error**: Generate a Fernet key and add it to `.env`:
  ```bash
  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  # Add the output as: ENCRYPTION_KEY=<value>
  ```
- **`UndefinedColumnError` / `column does not exist` on startup**: The database table is missing a column added in a recent model change. Run the required `ALTER TABLE` migration before redeploying (see section 9).
- **Webhook not receiving updates**: Check HTTPS, URL path `/webhook/telegram`, and firewall. Test with `curl -X POST https://your-domain.com/webhook/telegram -H "Content-Type: application/json" -d '{}'` (should return JSON, not a connection error).
- **DB connection errors**: Verify `DATABASE__HOST`, `DATABASE__PORT`, credentials, and that PostgreSQL allows connections from the app host. When running in Docker, `DATABASE__HOST` must be the container name (e.g. `db`), not `localhost`.
- **403 on webhook**: Ensure `X-Telegram-Bot-Api-Secret-Token` matches `WEBHOOK_SECRET_TOKEN` (or leave secret token empty for no verification).

## 9. Database schema migrations

`CREATE_TABLES_ON_STARTUP=true` (default) creates **new** tables automatically but **never modifies existing ones**. When a model gains a new column, you must apply the change manually before deploying the new image:

```bash
# Example: adding created_by_user_id column (added in commit 8355a9f)
docker exec bot-db-1 psql -U <DB_USER> -d <DB_NAME> -c \
  "ALTER TABLE organizer_table ADD COLUMN IF NOT EXISTS created_by_user_id BIGINT;"
```

General pattern for any new nullable column:
```sql
ALTER TABLE <table_name> ADD COLUMN IF NOT EXISTS <column_name> <type>;
```

**Migration checklist when deploying a new image:**
1. Check git log for model changes (`database/models.py`).
2. For each new column, run the corresponding `ALTER TABLE` on the live DB.
3. Deploy the new image (`docker compose up -d --build app`).

For a fully automated approach, consider adopting **Alembic** (see `MIGRATION_GUIDE.md`).
