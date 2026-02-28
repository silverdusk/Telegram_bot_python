# Manual: Deploy and Run the Project on a Server

This manual explains how to deploy the Telegram Bot (FastAPI) on a Linux server and run it. Choose one of the options below.

---

## What You Need Before Starting

- A **Linux server** (e.g. Ubuntu 22.04) with SSH access
- A **domain or IP** that points to your server (for webhook you need HTTPS, so a domain is recommended)
- A **Telegram Bot Token** from [@BotFather](https://t.me/BotFather)
- **PostgreSQL** — either on the same server or a separate one (managed DB is fine)

---

## Option A: Docker on Server (App + PostgreSQL in Docker)

Use this if you want the app and the database to run in Docker on the same machine.

### Step 1: Install Docker and Docker Compose on the server

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
# Log out and back in so the group change applies
```

Check:

```bash
docker --version
docker compose version
```

### Step 2: Upload the project to the server

From your **local machine** (in the project folder):

```bash
# Replace user and server with your SSH login and server address
rsync -avz --exclude '.git' --exclude '__pycache__' --exclude '.venv' \
  . user@your-server-ip:/opt/telegram-bot/
```

Or clone from Git on the server:

```bash
ssh user@your-server-ip
sudo mkdir -p /opt/telegram-bot
sudo chown $USER:$USER /opt/telegram-bot
cd /opt/telegram-bot
git clone https://github.com/your-username/Telegram_bot.git .
```

### Step 3: Create the `.env` file on the server

```bash
cd /opt/telegram-bot
cp .env.example .env
nano .env   # or use vim / any editor
```

Set at least these (replace with your real values):

```env
BOT_TOKEN=1234567890:ABCdefGHI...
DATABASE__DB_NAME=telegram_bot
DATABASE__USER=botuser
DATABASE__PASSWORD=your_secure_password
DATABASE__HOST=db
DATABASE__PORT=5432
DATABASE__TABLE_NAME=organizer_table
DEBUG=false
```

For webhook (after you have HTTPS), add:

```env
WEBHOOK_URL=https://your-domain.com/webhook/telegram
WEBHOOK_SECRET_TOKEN=some_random_secret_string
```

For the web admin panel, add:

```env
WEB_ADMIN_USER=admin
WEB_ADMIN_PASSWORD=your_strong_admin_password
# Generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
WEB_ADMIN_JWT_SECRET=your_random_hex_secret
```

> If `WEB_ADMIN_PASSWORD` is left empty, the admin login will always fail (panel is effectively disabled).

Save and exit.

### Step 4: Build and run with Docker Compose

```bash
cd /opt/telegram-bot
docker compose up -d
```

Check that the app and DB are running:

```bash
docker compose ps
docker compose logs -f app   # Ctrl+C to exit logs
```

### Step 5: Check that the app is running

On the server:

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/webhook/health
```

You should see JSON responses.

After setting up HTTPS (Step 6), the web admin panel is available at `https://your-domain.com/admin`.

### Step 6: Expose the app (for webhook)

You have two possibilities:

**A) Direct access (only for testing):**  
Open port 8000 in the firewall. The bot will work only over **HTTP**. Telegram webhooks require **HTTPS**, so for production use B.

**B) HTTPS with Nginx (recommended):**  
Install Nginx and SSL (e.g. Let’s Encrypt), then proxy to the app. See [“HTTPS and Nginx”](#https-and-nginx) below.

### Step 7: Set the Telegram webhook (HTTPS only)

After the app is reachable at `https://your-domain.com/webhook/telegram`:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain.com/webhook/telegram", "secret_token": "YOUR_WEBHOOK_SECRET_TOKEN"}'
```

Replace `<YOUR_BOT_TOKEN>` and `YOUR_WEBHOOK_SECRET_TOKEN` with the values from your `.env`.

### Useful commands (Option A)

```bash
# Stop
docker compose down

# Restart
docker compose restart app

# View logs
docker compose logs -f app

# Rebuild after code changes
docker compose up -d --build
```

---

## Option B: Docker on Server (App Only, External PostgreSQL)

Use this when PostgreSQL is **not** in Docker (e.g. another server or managed DB).

### Step 1: Install Docker

Same as Option A, Step 1.

### Step 2: Upload the project

Same as Option A, Step 2.

### Step 3: Create `.env` with external database

```bash
cd /opt/telegram-bot
cp .env.example .env
nano .env
```

Set **database host** to your real PostgreSQL host (IP or hostname):

```env
BOT_TOKEN=1234567890:ABCdefGHI...
DATABASE__DB_NAME=your_database_name
DATABASE__USER=your_db_user
DATABASE__PASSWORD=your_db_password
DATABASE__HOST=your-postgres-host.com
DATABASE__PORT=5432
DATABASE__TABLE_NAME=organizer_table
DEBUG=false
WEBHOOK_URL=https://your-domain.com/webhook/telegram
WEBHOOK_SECRET_TOKEN=your_secret_token
```

### Step 4: Run only the app (no DB container)

```bash
cd /opt/telegram-bot
docker compose -f docker-compose.app-only.yml up -d
```

Check:

```bash
docker compose -f docker-compose.app-only.yml ps
curl http://127.0.0.1:8000/webhook/health
```

### Step 5 and 6: Same as Option A

Expose the app (prefer HTTPS + Nginx) and set the Telegram webhook as in Option A, Steps 6 and 7.

---

## Option C: Run Without Docker (Poetry + systemd)

Use this when you prefer to run the app with Poetry and systemd (no Docker).

### Step 1: Install Python, Poetry, and PostgreSQL client

```bash
# Ubuntu 22.04
sudo apt update
sudo apt install -y python3.10 python3.10-venv python3-pip postgresql-client

# Install Poetry
curl -sSf https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

### Step 2: Upload the project

Same as Option A, Step 2 (e.g. `/opt/telegram-bot`).

### Step 3: Install dependencies and create `.env`

```bash
cd /opt/telegram-bot
poetry install --no-dev
cp .env.example .env
nano .env
```

Fill in the same variables as in Option A/B (use `DATABASE__HOST=localhost` if PostgreSQL is on the same server).

### Step 4: Create a system user and set permissions

```bash
sudo useradd -r -s /bin/false appuser
sudo chown -R appuser:appuser /opt/telegram-bot
```

### Step 5: Create a systemd service

```bash
sudo nano /etc/systemd/system/telegram-bot.service
```

Paste (adjust paths if different):

```ini
[Unit]
Description=Telegram Bot (FastAPI)
After=network.target postgresql.service

[Service]
Type=simple
User=appuser
Group=appuser
WorkingDirectory=/opt/telegram-bot
EnvironmentFile=/opt/telegram-bot/.env
ExecStart=/opt/telegram-bot/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

If you use Poetry’s venv in another path, replace `ExecStart` with the full path to `uvicorn` inside that venv, for example:

```ini
ExecStart=/opt/telegram-bot/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Step 6: Enable and start the service

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

Check:

```bash
curl http://127.0.0.1:8000/webhook/health
```

### Step 7: Expose and set webhook

Same as Option A: put Nginx (or another reverse proxy) in front with HTTPS, then set the webhook.

Useful commands:

```bash
sudo systemctl stop telegram-bot
sudo systemctl start telegram-bot
sudo systemctl restart telegram-bot
sudo journalctl -u telegram-bot -f
```

---

## HTTPS and Nginx

Telegram requires **HTTPS** for webhooks. Example setup with Nginx and Let’s Encrypt.

### 1. Install Nginx and Certbot

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 2. Get an SSL certificate

```bash
sudo certbot --nginx -d your-domain.com
```

Follow the prompts. Certbot will configure Nginx for HTTPS.

### 3. Add a server block for the bot

```bash
sudo nano /etc/nginx/sites-available/telegram-bot
```

Paste (replace `your-domain.com`):

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

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

Enable and test:

```bash
sudo ln -s /etc/nginx/sites-available/telegram-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 4. Set the webhook

```bash
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain.com/webhook/telegram", "secret_token": "YOUR_WEBHOOK_SECRET_TOKEN"}'
```

---

## Quick Reference: `.env` Variables

| Variable | Required | Example |
|----------|----------|---------|
| `BOT_TOKEN` | Yes | From BotFather |
| `DATABASE__DB_NAME` | Yes | `telegram_bot` |
| `DATABASE__USER` | Yes | `botuser` |
| `DATABASE__PASSWORD` | Yes | Strong password |
| `DATABASE__HOST` | Yes | `db` (Docker) or hostname/IP |
| `DATABASE__PORT` | Yes | `5432` |
| `DATABASE__TABLE_NAME` | Yes | `organizer_table` |
| `ENCRYPTION_KEY` | Yes | Fernet key (see DEPLOYMENT.md §2) |
| `WEBHOOK_URL` | For webhook | `https://your-domain.com/webhook/telegram` |
| `WEBHOOK_SECRET_TOKEN` | Recommended | Random string |
| `DEBUG` | No | `false` in production |
| `WEB_ADMIN_USER` | No | `admin` (default) |
| `WEB_ADMIN_PASSWORD` | For admin panel | Strong password — panel disabled if empty |
| `WEB_ADMIN_JWT_SECRET` | Recommended | 64-char hex string (`secrets.token_hex(32)`) |

---

## Troubleshooting

- **App does not start:** Check `.env` and that all `DATABASE__*` and `BOT_TOKEN` are set. For Docker: `docker compose logs app`. For systemd: `sudo journalctl -u telegram-bot -n 50`.
- **Database connection error:** Check `DATABASE__HOST`, `DATABASE__PORT`, user/password, and that PostgreSQL allows connections from the app (firewall, `pg_hba.conf`).
- **Webhook not receiving updates:** Bot must be reachable over **HTTPS** at `WEBHOOK_URL`. Test: `curl -X POST https://your-domain.com/webhook/telegram -H "Content-Type: application/json" -d '{}'` — you should get a JSON response, not a connection error.
- **403 on webhook:** The header `X-Telegram-Bot-Api-Secret-Token` must match `WEBHOOK_SECRET_TOKEN` in `.env` (or leave both empty to disable verification).
- **Admin panel login always fails:** Ensure `WEB_ADMIN_PASSWORD` is set in `.env`. The default is empty, which disables login. Also verify `WEB_ADMIN_USER` matches the username you enter.
- **Admin panel logs out on every restart:** `WEB_ADMIN_JWT_SECRET` is not set — a new random secret is generated each startup, invalidating all cookies. Set it to a fixed value in `.env`.

---

## Summary

1. Prepare server (Docker or Python + Poetry).
2. Upload project and create `.env` from `.env.example`.
3. Run app: **Docker** → `docker compose up -d` or `docker compose -f docker-compose.app-only.yml up -d`; **no Docker** → systemd service.
4. Put app behind **HTTPS** (e.g. Nginx + Let’s Encrypt).
5. Set Telegram webhook to `https://your-domain.com/webhook/telegram`.
6. Check health: `curl https://your-domain.com/webhook/health`.
7. Access admin panel: `https://your-domain.com/admin` (requires `WEB_ADMIN_PASSWORD` in `.env`).

After that, the bot runs on the server and receives updates via the webhook.
