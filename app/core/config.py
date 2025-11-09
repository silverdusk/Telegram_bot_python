"""Application configuration using Pydantic Settings."""
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    db_name: str = Field(..., description="Database name")
    user: str = Field(..., description="Database user")
    password: str = Field(..., description="Database password")
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    table_name: str = Field(..., description="Database table name")
    
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
    authorized_ids: List[int] = Field(default_factory=list, description="Authorized user IDs")
    allowed_types: List[str] = Field(
        default_factory=lambda: ["spare part", "miscellaneous"],
        description="Allowed item types"
    )
    
    # Validation settings
    min_len_str: int = Field(default=1, description="Minimum string length")
    max_len_str: int = Field(default=255, description="Maximum string length")
    skip_working_hours: bool = Field(default=True, description="Skip working hours check")
    
    # Database settings
    database: DatabaseSettings = Field(..., description="Database configuration")
    
    # FastAPI settings
    app_name: str = Field(default="Telegram Bot API", description="Application name")
    debug: bool = Field(default=False, description="Debug mode")
    webhook_url: str = Field(default="", description="Webhook URL for Telegram bot")
    webhook_secret_token: str = Field(default="", description="Secret token for webhook verification")
    
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
    """Get application settings."""
    global settings
    if settings is None:
        try:
            settings = Settings.from_json()
        except FileNotFoundError:
            # Fallback to environment variables
            settings = Settings()
    return settings

