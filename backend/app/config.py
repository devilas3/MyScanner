import os
import re
import socket
from functools import lru_cache
from pathlib import Path
from typing import List
from urllib.parse import parse_qsl, urlencode

from dotenv import load_dotenv
from pydantic import AnyHttpUrl, BaseModel

# Load .env from backend directory when running as app
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


def _resolve_postgres_host_to_ipv4(url: str) -> str:
    """Resolve hostname to IPv4 using regex only (urlparse calls ip_address(host) and fails on hostnames)."""
    if not url or not url.startswith("postgresql"):
        return url
    m = re.match(r"^(postgresql(?:\+\w+)?://[^@]+@)([^:/]+)(:\d+)?(/.*)?$", url)
    if not m:
        return url
    prefix, host, port_suffix, path_suffix = m.groups()
    port = 5432
    if port_suffix:
        port = int(port_suffix.lstrip(":"))
    try:
        __import__("ipaddress").ip_address(host)
        return url
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        if not infos:
            return url
        ip = infos[0][4][0]
        path_suffix = path_suffix or "/postgres"
        port_suffix = port_suffix or ""
        return f"{prefix}{ip}{port_suffix}{path_suffix}"
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

