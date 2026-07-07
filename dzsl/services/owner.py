import json
import os
import re
import time
from urllib.parse import quote

from dzsl.core.config import CONFIG_DIR, save_json
from dzsl.http import RequestError, request_json
from dzsl.services.listings import _base_url, listing_key, safe_http_url

SESSION_FILE = os.path.join(CONFIG_DIR, "owner_session.json")
SESSION_COOKIE = "dzsl_session"
OWNER_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) DZSL/1.0",
}

TEXT_LIMITS = {"name": 120, "description": 600, "rules": 1000}
URL_LIMITS = {"discord": 200, "banner": 300}

_TOKEN_RE = re.compile(r"^[0-9a-f]{16,128}$")


def dashboard_url(base_url=None):
    return f"{_base_url(base_url)}/dashboard"


def _valid_token(value):
    return isinstance(value, str) and bool(_TOKEN_RE.match(value))


def load_session(path=SESSION_FILE):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or not _valid_token(data.get("token")):
        return {}
    return data


def save_session(token, user=None, path=SESSION_FILE):
    if not _valid_token(token):
        raise ValueError("Invalid session token")
    user = user if isinstance(user, dict) else {}
    save_json(
        path,
        {
            "token": token,
            "steamId": str(user.get("steamId") or ""),
            "persona": str(user.get("persona") or ""),
            "savedAt": int(time.time()),
        },
    )


def clear_session(path=SESSION_FILE):
    try:
        os.unlink(path)
    except OSError:
        pass


def _auth_headers(token):
    if not _valid_token(token):
        raise RequestError("Not signed in", status=401)
    return {**OWNER_HEADERS, "Cookie": f"{SESSION_COOKIE}={token}"}


def auth_me(token, base_url=None, timeout=10):
    payload = request_json(
        f"{_base_url(base_url)}/api/auth/me",
        headers=_auth_headers(token),
        timeout=timeout,
    )
    user = payload.get("user") if isinstance(payload, dict) else None
    return user if isinstance(user, dict) else None


def logout(token, base_url=None, timeout=10):
    try:
        request_json(
            f"{_base_url(base_url)}/api/auth/logout",
            method="POST",
            headers=_auth_headers(token),
            timeout=timeout,
        )
    except RequestError:
        pass


def _clean_owner_listing(value):
    if not isinstance(value, dict):
        return None
    return {
        "name": value.get("name") or "",
        "description": value.get("description") or "",
        "rules": value.get("rules") or "",
        "discord": safe_http_url(value.get("discord")),
        "banner": safe_http_url(value.get("banner")),
        "promoted": value.get("promoted") is True,
    }


def _clean_claim_item(value):
    if not isinstance(value, dict):
        return None
    claim = value.get("claim")
    if not isinstance(claim, dict):
        return None
    key = listing_key(claim.get("serverKey"))
    if not key:
        return None
    return {
        "serverKey": key,
        "status": claim.get("status") or "pending",
        "claimToken": claim.get("token") or "",
        "verified": value.get("verified") is True,
        "verifiedExpiresAt": value.get("verifiedExpiresAt"),
        "gold": value.get("gold") is True,
        "goldUntil": value.get("goldUntil"),
        "goldStatus": value.get("goldStatus"),
        "listing": _clean_owner_listing(value.get("listing")),
    }


def fetch_claims(token, base_url=None, timeout=10):
    payload = request_json(
        f"{_base_url(base_url)}/api/claims",
        headers=_auth_headers(token),
        timeout=timeout,
    )
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise RequestError("Claims API returned invalid data")
    cleaned = []
    for value in items:
        item = _clean_claim_item(value)
        if item:
            cleaned.append(item)
    return cleaned


def clean_listing_fields(fields):
    if not isinstance(fields, dict):
        raise ValueError("Listing fields must be a mapping")
    cleaned = {}
    for key, limit in TEXT_LIMITS.items():
        if key in fields:
            value = fields[key] if isinstance(fields[key], str) else ""
            cleaned[key] = value.strip()[:limit]
    for key, limit in URL_LIMITS.items():
        if key in fields:
            value = safe_http_url(fields[key])[:limit]
            if fields[key] and str(fields[key]).strip() and not value:
                raise ValueError(f"{key} must be a valid http(s) URL")
            cleaned[key] = value
    return cleaned


def save_listing(token, server_key, fields, base_url=None, timeout=10):
    key = listing_key(server_key)
    if not key:
        raise ValueError(f"Invalid server key: {server_key!r}")
    payload = request_json(
        f"{_base_url(base_url)}/api/listings/{quote(key, safe='')}",
        method="PUT",
        json_body=clean_listing_fields(fields),
        headers=_auth_headers(token),
        timeout=timeout,
    )
    listing = payload.get("listing") if isinstance(payload, dict) else None
    if not isinstance(listing, dict):
        raise RequestError("Listing API returned invalid data")
    return _clean_owner_listing(listing)
