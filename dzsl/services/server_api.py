from urllib.parse import quote, urlsplit

from dzsl.core.uri import validate_host_port
from dzsl.http import RequestError, get_json


# Primary: our own feed (Valve master list via dayzlinux.com, ~0.3s).
# Fallback: the old DZSA community feed — bigger, slower, and throttled since
# the abandoned project's infrastructure started buckling (Jul 2026), but it
# still carries per-server mod lists, which our feed won't have until the
# client-side A2S layer lands.
DEFAULT_LIST_URL = "https://dayzlinux.com/api/feed"
FALLBACK_LIST_URL = "https://dayzsalauncher.com/api/v1/launcher/servers/dayz"
QUERY_URL = "https://dayzsalauncher.com/api/v1/query/{host}/{port}"
HEADERS = {"User-Agent": "DZSL/1.0"}


class ServerAPIError(RuntimeError):
    pass


def _https_url(value):
    parsed = urlsplit(value)
    local_http = parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if (
        (parsed.scheme != "https" and not local_http)
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ServerAPIError("Server API URL must be an HTTPS or local URL without credentials")
    return value


def _fetch_list(url, timeout):
    payload = get_json(_https_url(url), headers=HEADERS, timeout=timeout)
    servers = payload if isinstance(payload, list) else payload.get(
        "result", payload.get("servers", payload.get("data", []))
    )
    if not isinstance(servers, list) or not servers:
        raise ServerAPIError("Server API returned an invalid server list")
    return servers


def fetch_servers(url=DEFAULT_LIST_URL, timeout=30):
    try:
        return _fetch_list(url, timeout)
    except (ServerAPIError, RequestError):
        if url == FALLBACK_LIST_URL:
            raise
    return _fetch_list(FALLBACK_LIST_URL, timeout)


def fetch_server(host, port, timeout=12):
    host, port = validate_host_port(host, port)
    url = QUERY_URL.format(host=quote(host, safe=".:"), port=port)
    result = get_json(url, headers=HEADERS, timeout=timeout).get("result", {})
    if not isinstance(result, dict):
        raise ServerAPIError("Server API returned invalid server details")
    return result
