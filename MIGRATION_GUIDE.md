# Migration Guide: From pyTelegramBotAPI to FastAPI

This guide explains the changes made to convert the Telegram bot from `pyTelegramBotAPI` (polling) to FastAPI (webhook-based).

## Key Changes

### 1. Architecture
- **Before**: Polling-based bot using `pyTelegramBotAPI`
- **After**: Webhook-based bot using FastAPI and `python-telegram-bot` library

### 2. Dependencies
- Removed: `pyTelegramBotAPI`
- Added: `fastapi`, `uvicorn`, `python-telegram-bot`, `asyncpg`, `pydantic`, `pydantic-settings`, `pytz`

### 3. Project Structure
```
app/
├── api/
│   └── v1/
│       ├── webhook.py      # Webhook endpoint
│       └── handlers.py     # Bot handlers
├── core/
│   ├── config.py           # Pydantic settings
│   ├── dependencies.py     # FastAPI dependencies
│   └── validators.py       # Input validation
├── database/
│   ├── session.py          # Async database session
│   └── repository.py       # Database operations
├── schemas/
│   └── item.py             # Pydantic schemas
├── services/
│   └── bot_service.py      # Bot business logic
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
  "database": {
    "db_name": "your_db",
    "user": "your_user",
    "password": "your_password",
    "host": "localhost",
    "port": 5432,
    "table_name": "organizer_table",
    "db_url": "postgresql+asyncpg://user:password@host:port/db_name"
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

- `GET /` - Root endpoint
- `POST /webhook/telegram` - Telegram webhook endpoint
- `GET /webhook/health` - Health check endpoint

## Key Improvements

1. **Async/Await**: All operations are now asynchronous for better performance
2. **Type Safety**: Pydantic models provide type validation
3. **Dependency Injection**: Clean separation of concerns
4. **Repository Pattern**: Better database abstraction
5. **Webhook Support**: More scalable than polling
6. **FastAPI Features**: Automatic API documentation, validation, etc.

## Testing

The application can be tested using:
- FastAPI automatic docs at `http://localhost:8000/docs`
- Health check endpoint: `http://localhost:8000/webhook/health`
- Telegram webhook endpoint: `http://localhost:8000/webhook/telegram`

## Notes

- The old `bot/bot.py` file is kept for reference but is no longer used
- Database models have been updated to use SQLAlchemy 2.0 async patterns
- All handlers are now async functions
- Configuration supports both JSON file and environment variables

