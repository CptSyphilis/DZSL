"""Parsing helpers for links opened from the DayZ Linux website."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import unquote, urlsplit


_HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def _valid_host(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass

    if len(host) > 253:
        return False
    labels = host.rstrip(".").split(".")
    return bool(labels) and all(_HOST_LABEL.fullmatch(label) for label in labels)


def parse_connect_uri(value: str) -> tuple[str, int]:
    """Return the host and game port from a DZSL connect URI.

    Accepted form: ``dzsl://connect/<host>/<port>``.
    """

    if not isinstance(value, str) or not value:
        raise ValueError("empty DZSL link")

    parsed = urlsplit(value)
    if parsed.scheme.lower() != "dzsl":
        raise ValueError("unsupported link scheme")
    if parsed.netloc.lower() != "connect":
        raise ValueError("unsupported DZSL action")
    if parsed.query or parsed.fragment:
        raise ValueError("DZSL links cannot contain a query or fragment")

    parts = [unquote(part) for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise ValueError("connect link must contain a host and port")

    host = parts[0].strip()
    if not _valid_host(host):
        raise ValueError("invalid server host")

    try:
        port = int(parts[1], 10)
    except ValueError as exc:
        raise ValueError("invalid server port") from exc
    if not 1 <= port <= 65535:
        raise ValueError("server port must be between 1 and 65535")

    return host, port
