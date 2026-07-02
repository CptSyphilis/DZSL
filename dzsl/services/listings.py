import os
import threading
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from dzsl.http import RequestError, get_json


DEFAULT_DAYZLINUX_BASE_URL = "https://dayzlinux.com"
FEATURED_CACHE_TTL = 300
MAX_BANNER_BYTES = 4 * 1024 * 1024
LISTINGS_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) DZSL/1.0",
}

_cache_lock = threading.Lock()
_featured_cache = {}
_featured_cache_at = 0.0


def safe_http_url(value):
    if not isinstance(value, str):
        return ""
    value = value.strip()
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        return ""
    return value


def listing_key(value):
    if not isinstance(value, str):
        return ""
    value = value.strip().lower()
    host, separator, port = value.rpartition(":")
    if not separator or not host or not port.isdigit():
        return ""
    number = int(port)
    if not 1 <= number <= 65535:
        return ""
    return f"{host}:{number}"


def server_listing_key(server):
    endpoint = server.get("endpoint") or {}
    host = server.get("ip") or endpoint.get("ip") or ""
    port = server.get("port") or server.get("gamePort") or endpoint.get("port") or ""
    return listing_key(f"{host}:{port}")


def _clean_text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) and value.strip() else ""


def _clean_listing(value):
    if not isinstance(value, dict) or value.get("promoted") is not True:
        return None
    key = listing_key(value.get("serverKey"))
    if not key:
        return None
    return {
        "serverKey": key,
        "name": _clean_text(value.get("name"), 120),
        "description": _clean_text(value.get("description"), 600),
        "discord": safe_http_url(value.get("discord")),
        "banner": safe_http_url(value.get("banner")),
        "promoted": True,
        "updatedAt": value.get("updatedAt", 0),
    }


def _base_url(value=None):
    return (value or os.environ.get("DAYZLINUX_BASE_URL") or DEFAULT_DAYZLINUX_BASE_URL).rstrip("/")


def featured_listings(base_url=None, timeout=8, now=None):
    global _featured_cache, _featured_cache_at
    current = time.monotonic() if now is None else now
    with _cache_lock:
        if _featured_cache_at and current - _featured_cache_at < FEATURED_CACHE_TTL:
            return dict(_featured_cache)

    try:
        payload = get_json(
            f"{_base_url(base_url)}/api/listings",
            headers=LISTINGS_HEADERS,
            timeout=timeout,
        )
        featured = payload.get("featured") if isinstance(payload, dict) else None
        if not isinstance(featured, list):
            raise RequestError("Gold listing API returned invalid data")
        listings = {}
        for value in featured:
            listing = _clean_listing(value)
            if listing:
                listings[listing["serverKey"]] = listing
    except RequestError:
        with _cache_lock:
            if _featured_cache:
                return dict(_featured_cache)
        raise

    with _cache_lock:
        _featured_cache = listings
        _featured_cache_at = current
    return dict(listings)


def attach_featured_listings(servers, listings):
    for server in servers:
        server.pop("_gold_listing", None)
        listing = listings.get(server_listing_key(server))
        if listing:
            server["_gold_listing"] = listing
    return servers


def pin_featured_servers(servers):
    return sorted(servers, key=lambda server: "_gold_listing" not in server)


def fetch_banner(url, timeout=8, max_bytes=MAX_BANNER_BYTES):
    url = safe_http_url(url)
    if not url:
        raise RequestError("Invalid banner URL")
    request = Request(url, headers={"Accept": "image/*", "User-Agent": "DZSL/1"})
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310
            content_type = response.headers.get_content_type()
            if not content_type.startswith("image/"):
                raise RequestError("Banner URL did not return an image")
            data = response.read(max_bytes + 1)
    except (OSError, ValueError) as exc:
        raise RequestError(str(exc)) from exc
    if len(data) > max_bytes:
        raise RequestError("Banner image is too large")
    return data
