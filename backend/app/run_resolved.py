"""
Resolve DATABASE_URL hostname to IPv4, then start the app.
Use this as the Render start command so env is fixed before any code that
validates the host as an IP runs. We must NOT use urllib.parse.urlparse here
because Python's urlparse calls ip_address(hostname) internally and fails on hostnames.
"""
import os
import re
import socket


def _resolve_postgres_host_to_ipv4(url: str) -> str:
    """Extract host from postgres URL with regex (no urlparse), resolve to IPv4, replace in URL."""
    if not url or not url.startswith("postgresql"):
        return url
    # Match: postgresql[+driver]://...@HOST:port/path or ...@HOST/path (no urlparse - it calls ip_address(host))
    m = re.match(r"^(postgresql(?:\+\w+)?://[^@]+@)([^:/]+)(:\d+)?(/.*)?$", url)
    if not m:
        return url
    prefix, host, port_suffix, path_suffix = m.groups()
    port = 5432
    if port_suffix:
        port = int(port_suffix.lstrip(":"))
    try:
        __import__("ipaddress").ip_address(host)
        return url  # already an IP
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


def main():
    raw = os.environ.get("DATABASE_URL", "")
    if raw.startswith("postgresql"):
        os.environ["DATABASE_URL"] = _resolve_postgres_host_to_ipv4(raw)
    port = int(os.environ.get("PORT", "8000"))
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
