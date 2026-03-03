import os
import socket
from functools import lru_cache
from pathlib import Path
from typing import List
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from dotenv import load_dotenv
from pydantic import AnyHttpUrl, BaseModel

# Load .env from backend directory when running as app
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


def _resolve_postgres_host_to_ipv4(url: str) -> str:
    """Resolve hostname in PostgreSQL URL to IPv4 so runtimes that call ip_address(host) don't raise."""
    if not url.startswith("postgresql"):
        return url
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or 5432
    if not host:
        return url
    try:
        __import__("ipaddress").ip_address(host)
        return url  # already an IP
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        if not infos:
            return url
        resolved_ip = infos[0][4][0]
        netloc = parsed.netloc
        at = netloc.rfind("@") + 1
        rest = netloc[at:]
        colon = rest.find(":")
        host_part = rest[:colon] if colon >= 0 else rest
        suffix = rest[colon:] if colon >= 0 else ""
        new_netloc = netloc[:at] + resolved_ip + suffix
        new_url = urlunparse(parsed._replace(netloc=new_netloc))
        return new_url
    except (socket.gaierror, OSError):
        return url


def _get_database_url() -> str:
    raw = os.getenv("DATABASE_URL", "sqlite:///./scanner.db")
    if raw.startswith("postgresql"):
        resolved = _resolve_postgres_host_to_ipv4(raw)
        os.environ["DATABASE_URL"] = resolved
        return resolved
    return raw


class Settings(BaseModel):
    database_url: str = ...
    refresh_secret: str = os.getenv("REFRESH_SECRET", "changeme-refresh-secret")
    cors_origins: List[AnyHttpUrl] = []

    def __init__(self, **data):
        if "database_url" not in data:
            data["database_url"] = _get_database_url()
        super().__init__(**data)


@lru_cache
def get_settings() -> Settings:
    return Settings()

