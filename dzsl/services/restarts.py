import threading
import time
from urllib.parse import quote

from dzsl.core.config import RECENT_FILE, load_json
from dzsl.http import RequestError, get_json
from dzsl.services.listings import LISTINGS_HEADERS, _base_url

CACHE_TTL = 180
MAX_KEYS = 100
SOON_SECONDS = 15 * 60

_lock = threading.Lock()
_cache = {}
_fetched_at = 0.0


def _played_keys():
    keys = []
    for entry in load_json(RECENT_FILE) or []:
        ip = entry.get("ip") or entry.get("endpoint", {}).get("ip")
        port = entry.get("port") or entry.get("gamePort") or entry.get("endpoint", {}).get("port")
        if ip and port:
            keys.append(f"{ip}:{port}")
    return list(dict.fromkeys(keys))[:MAX_KEYS]


def played_restarts():
    global _cache, _fetched_at
    with _lock:
        if time.time() - _fetched_at < CACHE_TTL:
            return _cache
        keys = _played_keys()
        if not keys:
            return {}
        url = f"{_base_url()}/api/restarts?s={quote(','.join(keys), safe=',:.')}"
        try:
            payload = get_json(url, headers=LISTINGS_HEADERS, timeout=8)
            _cache = payload.get("servers") or {}
        except (RequestError, ValueError, AttributeError):
            pass
        _fetched_at = time.time()
        return _cache


def _span(seconds):
    minutes = max(1, int(seconds // 60))
    hours, minutes = divmod(minutes, 60)
    if not hours:
        return f"{minutes}m"
    if hours >= 24:
        return f"{hours // 24}d {hours % 24}h"
    return f"{hours}h {minutes:02d}m" if minutes else f"{hours}h"


def describe(info, now=None):
    if not info or not info.get("lastRestart"):
        return None
    now = now or time.time()
    up = now - info["lastRestart"] / 1000
    text = f"restarted {_span(up)} ago"
    if info.get("next") and info.get("every"):
        left = info["next"] / 1000 - now
        tip = (f"Restarts about every {_span(info['every'] / 1000)}, next in about {_span(left)}. "
               "Mod updates usually land on restart, so you may need to rejoin through DZSL.")
        return f"{text} · next {_span(left)}", tip, left <= SOON_SECONDS
    return text, "Not enough restarts seen yet to predict the next one.", False
