import gzip
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


class RequestError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status

    
def _json_request(url, method="GET", params=None, data=None, json_body=None, headers=None, timeout=30):
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
    body = None
    content_type = None
    if json_body is not None:
        body = json.dumps(json_body).encode()
        content_type = "application/json"
    elif data is not None:
        body = urlencode(data).encode()
        content_type = "application/x-www-form-urlencoded"
    request_headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        **(headers or {}),
    }
    if content_type is not None:
        request_headers["Content-Type"] = content_type
    request = Request(url, data=body, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310
            raw = response.read()
            if response.headers.get("Content-Encoding", "").lower() == "gzip":
                raw = gzip.decompress(raw)
            return json.loads(raw)
    except HTTPError as exc:
        raise RequestError(str(exc), status=exc.code) from exc
    except (URLError, OSError, ValueError) as exc:
        raise RequestError(str(exc)) from exc


def get_json(url, params=None, headers=None, timeout=30):
    return _json_request(url, params=params, headers=headers, timeout=timeout)


def post_form_json(url, data, headers=None, timeout=30):
    return _json_request(url, method="POST", data=data, headers=headers, timeout=timeout)


def request_json(url, method="GET", json_body=None, headers=None, timeout=30):
    return _json_request(url, method=method, json_body=json_body, headers=headers, timeout=timeout)
