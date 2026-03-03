"""
Resolve DATABASE_URL hostname to IPv4, then start the app.
Use this as the Render start command so env is fixed before any code that
validates the host as an IP runs:
  python -m app.run_resolved
"""
import os
import socket
from urllib.parse import urlparse, urlunparse


def _resolve_postgres_host_to_ipv4(url: str) -> str:
    if not url.startswith("postgresql") or not url:
        return url
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or 5432
    if not host:
        return url
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
        netloc = parsed.netloc
        at = netloc.rfind("@") + 1
        rest = netloc[at:]
        colon = rest.find(":")
        host_part = rest[:colon] if colon >= 0 else rest
        suffix = rest[colon:] if colon >= 0 else ""
        new_netloc = netloc[:at] + ip + suffix
        return urlunparse(parsed._replace(netloc=new_netloc))
    except (socket.gaierror, OSError):
        return url


def main():
    raw = os.environ.get("DATABASE_URL", "")
    if raw.startswith("postgresql"):
        os.environ["DATABASE_URL"] = _resolve_postgres_host_to_ipv4(raw)
    # Start uvicorn (same as: uvicorn app.main:app --host 0.0.0.0 --port $PORT)
    port = int(os.environ.get("PORT", "8000"))
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
