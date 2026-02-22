"""Application configuration using Pydantic Settings."""
import json
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    db_name: str = Field(..., description="Database name")
    user: str = Field(..., description="Database user")
    password: str = Field(..., description="Database password")
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    table_name: str = Field(..., description="Database table name")
    pool_size: int = Field(default=5, ge=1, le=100, description="SQLAlchemy connection pool size")
    max_overflow: int = Field(default=10, ge=0, le=100, description="SQLAlchemy pool max overflow")
    
    @property
    def db_url(self) -> str:
        """Construct database URL for asyncpg."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db_name}"
    
    @property
    def sync_db_url(self) -> str:
        """Construct synchronous database URL."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db_name}"


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Bot settings
    bot_token: str = Field(..., description="Telegram bot token")
    authorized_ids: List[int] = Field(default_factory=list, description="Fallback admin Telegram user IDs when DB unavailable (JSON: [123,456])")
    fallback_admin_ids: List[int] | None = Field(default=None, description="Override fallback admin IDs; if None, uses authorized_ids")
    encryption_key: str = Field(..., min_length=1, description="Base64 Fernet key for encrypting user data (required)")
    allowed_types: List[str] = Field(
        default_factory=lambda: ["spare part", "miscellaneous"],
        description="Allowed item types (JSON in env)"
    )

    @field_validator("authorized_ids", mode="before")
    @classmethod
    def parse_authorized_ids(cls, v: Union[List[int], str]) -> List[int]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v if v is not None else []

    @field_validator("fallback_admin_ids", mode="before")
    @classmethod
    def parse_fallback_admin_ids(cls, v: Union[List[int], str, None]) -> List[int] | None:
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v

    @property
    def effective_fallback_admin_ids(self) -> List[int]:
        """IDs treated as admin when user not in DB or DB unavailable."""
        if self.fallback_admin_ids is not None:
            return self.fallback_admin_ids
        return self.authorized_ids

    @field_validator("allowed_types", mode="before")
    @classmethod
    def parse_allowed_types(cls, v: Union[List[str], str]) -> List[str]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [x.strip() for x in v.split(",") if x.strip()]
        return v if v is not None else ["spare part", "miscellaneous"]
    
    # Validation settings
    min_len_str: int = Field(default=1, description="Minimum string length")
    max_len_str: int = Field(default=255, description="Maximum string length")
    max_item_amount: int = Field(default=1_000_000, ge=1, description="Maximum allowed item amount")
    max_item_price: float = Field(default=999_999.99, ge=0, description="Maximum allowed item price")
    skip_working_hours: bool = Field(default=True, description="Skip working hours check")
    
    # Database settings
    database: DatabaseSettings = Field(..., description="Database configuration")
    
    # FastAPI settings
    app_name: str = Field(default="Telegram Bot API", description="Application name")
    debug: bool = Field(default=False, description="Debug mode")
    webhook_url: str = Field(default="", description="Webhook URL for Telegram bot")
    webhook_secret_token: str = Field(default="", description="Secret token for webhook verification")
    create_tables_on_startup: bool = Field(default=True, description="Run create_all on startup (set false if using migrations)")
    cors_origins: List[str] = Field(
        default_factory=lambda: ["*"],
        description="CORS allow_origins (use ['*'] for all, or list of origins for production)",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[List[str], str]) -> List[str]:
        if isinstance(v, str):
            if v.strip() in ("*", ""):
                return ["*"]
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [x.strip() for x in v.split(",") if x.strip()]
        return v if v is not None else ["*"]
    
    @classmethod
    def from_json(cls, config_path: str = "./config.json") -> "Settings":
        """Load settings from JSON file (for backward compatibility)."""
        import json
        with open(config_path, 'r') as file:
            config_data = json.load(file)
        
        # Convert database dict to DatabaseSettings
        if isinstance(config_data.get("database"), dict):
            config_data["database"] = DatabaseSettings(**config_data["database"])
        
        # Convert skip_working_hours string to bool
        if isinstance(config_data.get("skip_working_hours"), str):
            config_data["skip_working_hours"] = config_data["skip_working_hours"].lower() == "true"
        
        return cls(**config_data)


# Global settings instance (will be initialized in main)
settings: Settings | None = None


def get_settings() -> Settings:
    """Load config: config.json if present (local), else .env / environment (e.g. Docker)."""
    global settings
    if settings is None:
        try:
            settings = Settings.from_json()
        except FileNotFoundError:
            settings = Settings()
    return settings

