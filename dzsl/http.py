import gzip
import http.client
import json
import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPSHandler, Request, build_opener


class RequestError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


# urllib tries resolved addresses sequentially with the full timeout each, so a
# broken IPv6 route stalls every request 30s+ per AAAA record before IPv4 is
# tried. Connect IPv4-first with a short per-address timeout instead.
def _connect_ipv4_first(host, port, timeout):
    infos = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    infos.sort(key=lambda info: info[0] != socket.AF_INET)
    last_err = None
    for family, socktype, proto, _, addr in infos:
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(min(5, timeout) if timeout else 5)
        try:
            sock.connect(addr)
            sock.settimeout(timeout)
            return sock
        except OSError as exc:
            last_err = exc
            sock.close()
    raise last_err if last_err else OSError(f"could not connect to {host}:{port}")


class _IPv4FirstHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        self.sock = _connect_ipv4_first(self.host, self.port, self.timeout)
        if self._tunnel_host:
            self._tunnel()
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


class _IPv4FirstHTTPSHandler(HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_IPv4FirstHTTPSConnection, req, context=self._context)


_opener = build_opener(_IPv4FirstHTTPSHandler(context=ssl.create_default_context()))

    
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
        with _opener.open(request, timeout=timeout) as response:  # nosec B310
            raw = response.read()
            if response.headers.get("Content-Encoding", "").lower() == "gzip":
                raw = gzip.decompress(raw)
            return json.loads(raw)
    except HTTPError as exc:
        raise RequestError(str(exc), status=exc.code) from exc
    except (URLError, OSError, ValueError) as exc:
        raise RequestError(str(exc)) from exc


def get_text(url, headers=None, timeout=30):
    request = Request(url, headers={"Accept-Encoding": "gzip", **(headers or {})})
    try:
        with _opener.open(request, timeout=timeout) as response:  # nosec B310
            raw = response.read()
            if response.headers.get("Content-Encoding", "").lower() == "gzip":
                raw = gzip.decompress(raw)
            return raw.decode("utf-8", "replace")
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


def download_file(url, dest, progress=None, timeout=30):
    request = Request(url)
    try:
        with _opener.open(request, timeout=timeout) as response, open(dest, "wb") as out:  # nosec B310
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            while chunk := response.read(1 << 16):
                out.write(chunk)
                done += len(chunk)
                if progress and total:
                    progress(done / total)
    except HTTPError as exc:
        raise RequestError(str(exc), status=exc.code) from exc
    except (URLError, OSError, ValueError) as exc:
        raise RequestError(str(exc)) from exc
