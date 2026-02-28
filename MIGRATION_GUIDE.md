# Migration Guide: From pyTelegramBotAPI to FastAPI

This guide explains the changes made to convert the Telegram bot from `pyTelegramBotAPI` (polling) to FastAPI (webhook-based).

## Key Changes

### 1. Architecture
- **Before**: Polling-based bot using `pyTelegramBotAPI`
- **After**: Webhook-based bot using FastAPI and `python-telegram-bot` library

### 2. Dependencies
- Removed: `pyTelegramBotAPI`
- Added: `fastapi`, `uvicorn`, `python-telegram-bot`, `asyncpg`, `pydantic`, `pydantic-settings`, `pytz`, `jinja2`, `PyJWT`, `cryptography`

### 3. Project Structure
```
app/
├── api/
│   └── v1/
│       ├── webhook.py      # Telegram webhook endpoint
│       ├── handlers.py     # Bot handlers
│       └── admin.py        # Web admin panel routes + auth middleware
├── core/
│   ├── config.py           # Pydantic settings
│   ├── dependencies.py     # FastAPI dependencies
│   ├── permissions.py      # Role/permission helpers
│   └── validators.py       # Input validation
├── database/
│   ├── session.py          # Async database session
│   └── repository.py       # Database operations
├── schemas/
│   └── item.py             # Pydantic schemas
├── services/
│   └── bot_service.py      # Bot business logic
├── static/
│   └── admin.css           # Web admin panel styles
├── templates/              # Jinja2 HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── users.html
│   ├── items.html
│   └── settings.html
└── main.py                 # FastAPI application
```

### 4. Database Layer
- Converted to async SQLAlchemy 2.0
- Uses `asyncpg` for async PostgreSQL operations
- Repository pattern for database operations
- Dependency injection for database sessions

### 5. Configuration
- Uses Pydantic Settings for configuration management
- Supports both JSON file (backward compatible) and environment variables
- Type-safe configuration with validation

## Setup Instructions

### 1. Install Dependencies
```bash
poetry install
```

### 2. Configure Environment
Create a `.env` file or use `config.json` (backward compatible):
```json
{
  "bot_token": "YOUR_BOT_TOKEN",
  "encryption_key": "YOUR_FERNET_KEY",
  "database": {
    "db_name": "your_db",
    "user": "your_user",
    "password": "your_password",
    "host": "localhost",
    "port": 5432,
    "table_name": "organizer_table"
  },
  "authorized_ids": [1234567890],
  "min_len_str": 1,
  "max_len_str": 255,
  "skip_working_hours": true,
  "allowed_types": ["spare part", "miscellaneous"],
  "webhook_url": "https://your-domain.com/webhook/telegram",
  "webhook_secret_token": "your_secret_token"
}
```

> `encryption_key` is **required**. Generate one with:
> ```bash
> python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
> ```
> Store it securely — it is used to encrypt sensitive user data at rest. Changing or losing it makes existing encrypted data unreadable.

### 3. Run the Application
```bash
# Using Poetry
poetry run python run.py

# Or directly with uvicorn
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Set Up Webhook
After starting the application, set the webhook URL:
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain.com/webhook/telegram", "secret_token": "your_secret_token"}'
```

Or use the Telegram Bot API directly:
```python
from telegram import Bot
import asyncio

async def set_webhook():
    bot = Bot(token="YOUR_BOT_TOKEN")
    await bot.set_webhook(
        url="https://your-domain.com/webhook/telegram",
        secret_token="your_secret_token"
    )

asyncio.run(set_webhook())
```

## API Endpoints

### Telegram bot
- `GET /` - Root endpoint
- `POST /webhook/telegram` - Telegram webhook endpoint
- `GET /webhook/health` - Health check endpoint

### Web admin panel
- `GET /admin/login` — Login page
- `POST /admin/login` — Authenticate (sets httponly JWT cookie)
- `POST /admin/logout` — Logout (clears cookie)
- `GET /admin` — Dashboard (user/item counts)
- `GET /admin/users` — List users
- `POST /admin/users` — Add user
- `POST /admin/users/role` — Change user role
- `POST /admin/users/delete` — Delete user
- `GET /admin/items` — Browse items (paginated)
- `GET /admin/settings` — View bot settings
- `POST /admin/settings` — Save bot settings

## Key Improvements

1. **Async/Await**: All operations are now asynchronous for better performance
2. **Type Safety**: Pydantic models provide type validation
3. **Dependency Injection**: Clean separation of concerns
4. **Repository Pattern**: Better database abstraction
5. **Webhook Support**: More scalable than polling
6. **FastAPI Features**: Automatic API documentation, validation, etc.
7. **Web Admin Panel**: Browser-based UI for user management, item browsing, and settings

## Testing

The application can be tested using:
- FastAPI automatic docs at `http://localhost:8000/docs`
- Health check endpoint: `http://localhost:8000/webhook/health`
- Telegram webhook endpoint: `http://localhost:8000/webhook/telegram`
- Web admin panel: `http://localhost:8000/admin`

Run the test suite:
```bash
poetry run pytest          # 155 tests (excludes legacy test_bot.py, test_database.py)
poetry run pytest -v       # verbose output
```

Legacy test files `tests/test_bot.py` and `tests/test_database.py` are excluded via `pyproject.toml` — they reference the old `pyTelegramBotAPI` classes that no longer exist.

## Notes

- The old `bot/bot.py` file is kept for reference but is no longer used
- Database models have been updated to use SQLAlchemy 2.0 async patterns
- All handlers are now async functions
- Configuration supports both JSON file and environment variables

## Schema migration history

`CREATE_TABLES_ON_STARTUP=true` creates missing tables on boot but **never alters existing ones**. When deploying to an existing database, run the relevant `ALTER TABLE` statements first.

| Commit | Change | Migration SQL |
|--------|--------|---------------|
| `8355a9f` | Added `created_by_user_id` column to `organizer_table` | `ALTER TABLE organizer_table ADD COLUMN IF NOT EXISTS created_by_user_id BIGINT;` |

For future changes: add a row here whenever a new column is added to a model, so deployments don't miss it.

