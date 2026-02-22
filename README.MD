# Telegram Bot Project

A Telegram bot for item management: add items, list them, and update availability. Built with **FastAPI** and **python-telegram-bot** in **webhook** mode.

**→ [Deploy and run on a server (manual)](docs/DEPLOY_MANUAL.md)**  
**→ [Deployment guide (Docker, webhook, HTTPS)](DEPLOYMENT.md)**

## Features

- **Item management**: Add items (name, amount, type, price, availability), get list of your items, **remove items by name**, change availability by item name.
- **Conversation flow**: Multi-step Add flow with inline buttons for type and availability; optional text input; cancel with `/cancel`. Remove-item flow: enter name → items matching that name (for the current chat) are deleted.
- **Menus**: Reply keyboard after `/start`; compact inline menu via `/menu` (Get, Add, Remove item, Admin, Change availability, Send test message, Stop).
- **Validation**: Length and character rules for names; amount/price range checks; working-hours check for Add (configurable).
- **Authorization**: Stop command restricted to configured user IDs.
- **Logging**: Structured logging (no secrets or user content in logs).

## Project structure

```
app/
  main.py              # FastAPI app, lifespan, routes
  api/v1/
    handlers.py        # Command and message handlers, callback routing
    webhook.py         # POST /webhook/telegram, health
  core/
    config.py         # Settings (env / config.json)
    validators.py     # validate_text_input, is_int, is_float, check_working_hours
  database/
    session.py        # Async engine, session
    repository.py     # Item CRUD (incl. delete_by_name_and_chat)
  services/
    bot_service.py    # Bot logic: welcome, menu, add/get/remove/availability, keyboards
  schemas/
    item.py           # ItemCreate, ItemResponse, ItemUpdate
database/             # Legacy DB layer (optional)
bot/                  # Legacy Telebot-based bot (optional)
tests/
  conftest.py         # Fixtures (mock_settings, mock_bot, mock_context)
  test_validators.py  # Validators
  test_app_bot_service.py  # clear_flow_state, keyboards, handle_remove_item, process_remove_item
  test_app_repository.py   # delete_by_name_and_chat
  test_schemas.py     # ItemCreate, ItemUpdate
```

## Requirements

- Python 3.10+
- Poetry
- PostgreSQL 12+
- For production: HTTPS (Telegram webhooks require TLS)

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/silverdusk/Telegram_bot_python.git
   cd Telegram_bot_python
   ```

2. **Install dependencies**
   ```bash
   poetry install
   ```

3. **Configuration**  
   Either use a **`.env`** file (recommended for Docker and server) or **`config.json`** (legacy/local).

   - **Option A – .env**  
     Copy the example and set at least `BOT_TOKEN` and database settings:
     ```bash
     cp .env.example .env
     # Edit .env: BOT_TOKEN, DATABASE (or DATABASE__DB_NAME, DATABASE__USER, etc.)
     ```
     For webhook on a server, set `WEBHOOK_URL` and optionally `WEBHOOK_SECRET_TOKEN`.

   - **Option B – config.json**  
     If `config.json` exists in the project root, it takes precedence. Use `config.json.example` as a template.

4. **Database**  
   Create a PostgreSQL database and table (see [PostgreSQL setup](#postgresql-setup) below). The app can create tables on startup if `CREATE_TABLES_ON_STARTUP` is true (default).

## Running

### Local (development)

```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or:

```bash
poetry run python -m app.main
```

For production you must run behind HTTPS and set the Telegram webhook (see [DEPLOYMENT.md](DEPLOYMENT.md)).

### Docker

```bash
# With PostgreSQL in Docker
docker compose up -d

# App only (use existing DB)
# Set DATABASE__HOST etc. in .env
docker compose -f docker-compose.app-only.yml up -d
```

- App: `http://localhost:8000`
- Health: `http://localhost:8000/webhook/health`

### Webhook

Telegram must send updates to your server. After the app is reachable over **HTTPS**:

```bash
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain.com/webhook/telegram", "secret_token": "YOUR_WEBHOOK_SECRET_TOKEN"}'
```

Leave `WEBHOOK_SECRET_TOKEN` empty in `.env` if you do not use a secret.

**Important – secret token and 403:**  
If you set the webhook **without** a secret (no `secret_token` in the `curl` above), you must **remove or leave empty** `WEBHOOK_SECRET_TOKEN` in `.env` and restart the app. If the app has a secret set but Telegram sends requests without it (or with a different one), the app returns **403** and the bot will not reply even though the webhook is called. See [DEPLOYMENT.md – Troubleshooting](DEPLOYMENT.md#8-troubleshooting) for more.

## Configuration

Main variables (env or `config.json`):

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Telegram bot token (required) |
| `DATABASE__*` or `DATABASE` | DB name, user, password, host, port, table_name |
| `AUTHORIZED_IDS` | JSON array of Telegram user IDs allowed to use Stop |
| `ALLOWED_TYPES` | Item types, e.g. `["spare part", "miscellaneous"]` |
| `MIN_LEN_STR`, `MAX_LEN_STR` | Min/max length for text fields (default 1, 255) |
| `MAX_ITEM_AMOUNT`, `MAX_ITEM_PRICE` | Upper bounds for amount and price |
| `SKIP_WORKING_HOURS` | If true, Add is allowed anytime |
| `WEBHOOK_URL` | Full URL for webhook (e.g. `https://your-domain.com/webhook/telegram`) |
| `WEBHOOK_SECRET_TOKEN` | Optional secret for webhook verification |

See `.env.example` for a full list.

## Tests

```bash
poetry run python -m pytest tests/test_validators.py tests/test_app_bot_service.py tests/test_app_repository.py tests/test_schemas.py -v
```

Run all tests:

```bash
poetry run python -m pytest tests/ -v
```

## Logging

- Default: stdout with level INFO. In Docker, logs go to the console and optionally to `/app/logs/log.log` if configured.
- Optional: put `logging.ini` in the project root to customize format and handlers.

## PostgreSQL setup

1. Create a database and user, then a table, for example:

   ```sql
   CREATE DATABASE telegram_bot;
   CREATE USER botuser WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE telegram_bot TO botuser;
   ```

2. Create the table (or let the app create it on startup):

   ```sql
   CREATE TABLE organizer_table (
       id SERIAL PRIMARY KEY,
       item_name VARCHAR(255),
       item_amount INTEGER,
       item_type VARCHAR(255),
       item_price NUMERIC,
       availability BOOLEAN,
       chat_id BIGINT,
       timestamp TIMESTAMP WITHOUT TIME ZONE
   );
   GRANT ALL ON TABLE organizer_table TO botuser;
   GRANT USAGE, SELECT ON SEQUENCE organizer_table_id_seq TO botuser;
   ```

3. Set in `.env` (or equivalent):

   - `DATABASE__DB_NAME=telegram_bot`
   - `DATABASE__USER=botuser`
   - `DATABASE__PASSWORD=...`
   - `DATABASE__HOST=localhost` (or `db` in Docker)
   - `DATABASE__PORT=5432`
   - `DATABASE__TABLE_NAME=organizer_table`

For a more detailed PostgreSQL and pgAdmin setup, see the previous version of this README or your deployment notes.

## Troubleshooting (webhook)

- **Bot doesn’t respond to /start or commands**  
  1. Confirm the webhook is set: `curl -s "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"` (see `result.url`).  
  2. Confirm the app is reachable: `curl -X POST https://your-domain.com/webhook/telegram -H "Content-Type: application/json" -d '{}'` (you should get a JSON response, not a connection error).  
  3. **403 from webhook** → Secret token mismatch: if you registered the webhook without a secret, remove or leave empty `WEBHOOK_SECRET_TOKEN` in `.env` and recreate/restart the app container so the new env is loaded.  
- More details: [DEPLOYMENT.md § Troubleshooting](DEPLOYMENT.md#8-troubleshooting).

## Documentation

- **[DEPLOYMENT.md](DEPLOYMENT.md)** – Docker, webhook, HTTPS, checklist.
- **[docs/DEPLOY_MANUAL.md](docs/DEPLOY_MANUAL.md)** – Manual server deployment.
- **[docs/DIALOGUE_FLOW_REVIEW.md](docs/DIALOGUE_FLOW_REVIEW.md)** – Dialogue flow and improvement notes.
- **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** – Moving from Telebot to FastAPI/webhook.
