import os
from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import AnyHttpUrl, BaseModel

# Load .env from backend directory when running as app
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


class Settings(BaseModel):
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./scanner.db")
    refresh_secret: str = os.getenv("REFRESH_SECRET", "changeme-refresh-secret")
    cors_origins: List[AnyHttpUrl] = []


@lru_cache
def get_settings() -> Settings:
    return Settings()

