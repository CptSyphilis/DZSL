import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


class RequestError(RuntimeError):
    pass


def _json_request(url, method="GET", params=None, data=None, headers=None, timeout=30):
    parsed = urlsplit(url)
    local_http = parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if (
        (parsed.scheme != "https" and not local_http)
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise RequestError("Only HTTPS or local development URLs without embedded credentials are allowed")
    if params:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode(params)}"
    body = urlencode(data).encode() if data is not None else None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = Request(url, data=body, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310
            return json.load(response)
    except (HTTPError, URLError, OSError, ValueError) as exc:
        raise RequestError(str(exc)) from exc


def get_json(url, params=None, headers=None, timeout=30):
    return _json_request(url, params=params, headers=headers, timeout=timeout)


def post_form_json(url, data, headers=None, timeout=30):
    return _json_request(url, method="POST", data=data, headers=headers, timeout=timeout)
