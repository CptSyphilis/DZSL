# A2S (Source query) over plain UDP — no Steamworks, so Steam never thinks DayZ is running.
import socket
import struct
import time

from dzsl.core.logging import get_logger

log = get_logger("a2s")

_INFO_REQUEST = b"\xFF\xFF\xFF\xFFTSource Engine Query\x00"
_TIMEOUT = 2.0


class A2SError(RuntimeError):
    pass


class _Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def remaining(self):
        return len(self.data) - self.pos

    def bytes(self, n):
        if self.remaining() < n:
            raise A2SError("A2S payload truncated")
        out = self.data[self.pos:self.pos + n]
        self.pos += n
        return out

    def u8(self):
        return self.bytes(1)[0]

    def u16(self):
        return struct.unpack("<H", self.bytes(2))[0]

    def u32(self):
        return struct.unpack("<I", self.bytes(4))[0]

    def u64(self):
        return struct.unpack("<Q", self.bytes(8))[0]

    def zstring(self):
        end = self.data.find(b"\x00", self.pos)
        if end < 0:
            raise A2SError("Unterminated string in A2S payload")
        out = self.data[self.pos:end]
        self.pos = end + 1
        return out.decode("utf-8", "replace")


def _recv_payload(sock):
    fragments = {}
    total = None
    deadline = time.monotonic() + _TIMEOUT
    while True:
        sock.settimeout(max(0.05, deadline - time.monotonic()))
        packet = sock.recv(65535)
        header = struct.unpack("<i", packet[:4])[0]
        if header == -1:
            return packet[4:]
        if header != -2:
            raise A2SError(f"Unknown A2S packet header {header}")
        pkt_id, count, number, _size = struct.unpack("<iBBH", packet[4:12])
        if pkt_id & 0x80000000:
            raise A2SError("Compressed A2S split packets not supported")
        fragments[number] = packet[12:]
        total = count
        if len(fragments) == total:
            data = b"".join(fragments[i] for i in range(total))
            if data[:4] == b"\xFF\xFF\xFF\xFF":
                data = data[4:]
            return data


def _exchange(sock, addr, request):
    payload = None
    challenge = b"\xFF\xFF\xFF\xFF"
    for _ in range(4):
        if request == _INFO_REQUEST and challenge == b"\xFF\xFF\xFF\xFF":
            sock.sendto(request, addr)
        elif request == _INFO_REQUEST:
            sock.sendto(request + challenge, addr)
        else:
            sock.sendto(b"\xFF\xFF\xFF\xFF" + request + challenge, addr)
        started = time.monotonic()
        payload = _recv_payload(sock)
        elapsed = time.monotonic() - started
        if payload[:1] == b"A":  # S2C_CHALLENGE
            challenge = payload[1:5]
            continue
        return payload, elapsed
    raise A2SError("Server kept sending challenges")


def query_info(host, port, timeout=_TIMEOUT):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        try:
            payload, elapsed = _exchange(sock, (host, port), _INFO_REQUEST)
        except (OSError, struct.error) as exc:
            raise A2SError(str(exc)) from exc
    if payload[:1] != b"I":
        raise A2SError(f"Unexpected A2S_INFO response {payload[:1]!r}")
    r = _Reader(payload[1:])
    info = {
        "protocol": r.u8(),
        "name": r.zstring(),
        "map": r.zstring(),
        "folder": r.zstring(),
        "game": r.zstring(),
        "appid": r.u16(),
        "players": r.u8(),
        "max_players": r.u8(),
        "bots": r.u8(),
        "server_type": chr(r.u8()),
        "environment": chr(r.u8()),
        "password": bool(r.u8()),
        "vac": bool(r.u8()),
        "version": r.zstring(),
        "ping": int(elapsed * 1000),
    }
    if r.remaining():
        edf = r.u8()
        if edf & 0x80:
            info["game_port"] = r.u16()
        if edf & 0x10:
            r.u64()
        if edf & 0x40:
            r.u16()
            r.zstring()
        if edf & 0x20:
            info["keywords"] = r.zstring()
        if edf & 0x01:
            r.u64()
    return info


def query_rules_raw(host, port, timeout=_TIMEOUT):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        try:
            payload, _ = _exchange(sock, (host, port), b"V")
        except (OSError, struct.error) as exc:
            raise A2SError(str(exc)) from exc
    if payload[:1] != b"E":
        raise A2SError(f"Unexpected A2S_RULES response {payload[:1]!r}")
    data = payload[1:]
    count = struct.unpack("<H", data[:2])[0]
    pairs = []
    pos = 2
    for _ in range(count):
        end = data.find(b"\x00", pos)
        key = data[pos:end]
        pos = end + 1
        end = data.find(b"\x00", pos)
        pairs.append((key, data[pos:end]))
        pos = end + 1
    return pairs


def _unescape(data):
    # DayZ escapes: 01 01→01, 01 02→00, 01 03→FF
    out = bytearray()
    i = 0
    while i < len(data):
        b = data[i]
        if b == 0x01 and i + 1 < len(data):
            nxt = data[i + 1]
            if nxt == 0x01:
                out.append(0x01)
            elif nxt == 0x02:
                out.append(0x00)
            elif nxt == 0x03:
                out.append(0xFF)
            else:
                out.append(b)
                out.append(nxt)
            i += 2
            continue
        out.append(b)
        i += 1
    return bytes(out)


def query_mods(host, port, timeout=_TIMEOUT):
    # blob: ver u8, overflow u8, 2 DLC bytes, count u8, per mod: hash u32, id-width u8, id, name
    pairs = query_rules_raw(host, port, timeout)
    chunks = {k[0]: v for k, v in pairs if len(k) == 2 and k[0] <= k[1]}
    if not chunks:
        return []
    blob = _unescape(b"".join(chunks[i] for i in sorted(chunks)))
    r = _Reader(blob)
    r.bytes(4)
    count = r.u8()
    mods = []
    for _ in range(count):
        r.u32()  # load-order hash
        id_width = r.u8()
        workshop_id = int.from_bytes(r.bytes(id_width or 4), "little")
        name = r.bytes(r.u8()).decode("utf-8", "replace")
        mods.append({"steamWorkshopId": workshop_id, "name": name})
    return mods


if __name__ == "__main__":
    import json
    import sys

    host, port = sys.argv[1], int(sys.argv[2])
    print(json.dumps(query_info(host, port), indent=2))
    if "--raw" in sys.argv:
        for k, v in query_rules_raw(host, port):
            print(k.hex(), "=", v.hex()[:120])
    else:
        for m in query_mods(host, port):
            print(m["steamWorkshopId"], m["name"])
