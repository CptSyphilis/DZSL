from urllib.parse import quote, urlsplit

from dzsl.core.uri import validate_host_port
from dzsl.http import get_json


DEFAULT_LIST_URL = "https://dayzsalauncher.com/api/v1/launcher/servers/dayz"
QUERY_URL = "https://dayzsalauncher.com/api/v1/query/{host}/{port}"
HEADERS = {"User-Agent": "DZSL/1.0"}


class ServerAPIError(RuntimeError):
    pass


def _https_url(value):
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ServerAPIError("Server API URL must be an HTTPS URL without credentials")
    return value


def fetch_servers(url=DEFAULT_LIST_URL, timeout=30):
    payload = get_json(_https_url(url), headers=HEADERS, timeout=timeout)
    servers = payload if isinstance(payload, list) else payload.get(
        "result", payload.get("servers", payload.get("data", []))
    )
    if not isinstance(servers, list):
        raise ServerAPIError("Server API returned an invalid server list")
    return servers


def fetch_server(host, port, timeout=12):
    host, port = validate_host_port(host, port)
    url = QUERY_URL.format(host=quote(host, safe=".:"), port=port)
    result = get_json(url, headers=HEADERS, timeout=timeout).get("result", {})
    if not isinstance(result, dict):
        raise ServerAPIError("Server API returned invalid server details")
    return result
