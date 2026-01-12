from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Union


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
        json_schema_extra={
            "ALLOWED_ORIGINS": {"description": "Comma-separated list of allowed origins"}
        }
    )

    PROJECT_NAME: str = "BCom AI Services API"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # PostgreSQL Database Configuration
    DATABASE_URL: str  # e.g., postgresql+psycopg://postgres:P%40ssw0rd@localhost:5432/bcai

    # JWT Secret and Configuration
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS Configuration - comma-separated string or list
    ALLOWED_ORIGINS: Union[List[str], str] = "*"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        """Parse ALLOWED_ORIGINS from comma-separated string or list"""
        if isinstance(v, str):
            origins = [origin.strip() for origin in v.split(",") if origin.strip()]
            return origins if origins else ["*"]
        if isinstance(v, list):
            return v
        return ["*"]


settings = Settings()
