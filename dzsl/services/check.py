from collections import Counter

from dzsl.services.a2s import A2SError, query_info, query_mods
from dzsl.services.dayz import installed_version, same_major
from dzsl.services.server_api import fetch_servers

WIKI = "https://community.bistudio.com/wiki/DayZ:Server_Configuration"
FIREWALL_TIP = (
    "Make sure the server is running, then open both its game port and its Steam query port "
    "(steamQueryPort in serverDZ.cfg, 27016 by default) for UDP in your firewall and your host's "
    "control panel. Steam takes a few minutes to list a server after it starts."
)


def _result(level, title, detail, link=None):
    item = {"level": level, "title": title, "detail": detail}
    if link:
        item["link"] = {"label": "Server configuration guide", "url": link}
    return item


def private_ip_reason(ip):
    a, b = (int(x) for x in ip.split(".")[:2])
    if a == 10 or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 168):
        return ("This is a home or office network (LAN) address. Players need your server's public IP. "
                "Your host's panel shows it, or search \"what is my IP\" on the machine running the server.")
    if a in (0, 127):
        return "This address only points at your own machine. Use the server's public IP."
    if a == 100 and 64 <= b <= 127:
        return ("This is a carrier-grade NAT address: your internet provider shares one public IP between many "
                "customers, so players can't reach a server behind it. Ask your provider for a public IP, or host somewhere else.")
    if a == 169 and b == 254:
        return "This is a self-assigned address, which usually means the machine has no working network. Use the server's public IP."
    if a >= 224:
        return "This isn't a normal server address. Use the server's public IP."
    return None


def _ver(value):
    return tuple(int(p) for p in str(value).split(".") if p.isdigit())


def _common_version(servers):
    counts = Counter(s.get("version") for s in servers if s.get("players") and s.get("version"))
    return counts.most_common(1)[0][0] if counts else None


def _ip(s):
    return s.get("ip") or s.get("endpoint", {}).get("ip")


def _game_port(s):
    return s.get("gamePort") or s.get("endpoint", {}).get("port")


def _probe(ip, ports, game_port):
    for qp in ports:
        try:
            info = query_info(ip, qp, timeout=2)
        except (A2SError, OSError, ValueError):
            continue
        if not info.get("game_port") or info.get("game_port") == game_port:
            return qp, info
    return None, None


def check_server(cfg, ip, port, servers=None):
    reason = private_ip_reason(ip)
    if reason:
        return {"server": None, "results": [_result("error", "That's not a public IP", reason)]}

    servers = servers or fetch_servers(timeout=15)
    on_ip = [s for s in servers if _ip(s) == ip]
    s = next((x for x in on_ip if _game_port(x) == port), None)
    results = []

    if not s:
        by_query = next((x for x in on_ip if x.get("queryPort") == port), None)
        if by_query:
            results.append(_result(
                "error", "That's the query port, not the game port",
                f"Port {port} is the Steam query port of \"{by_query.get('name')}\". Players and DZSL use the game port, "
                f"which is {_game_port(by_query)}. Check again with port {_game_port(by_query)}.",
            ))
            return {"server": None, "results": results}
        qp, info = _probe(ip, [27016, port + 1, port + 24714], port)
        if info:
            results.append(_result(
                "warn", "Server answers, but isn't in the server list",
                f"\"{info.get('name')}\" answers on query port {qp}, but Steam's list doesn't show it yet. "
                "Steam takes a few minutes to list a new server. If it stays missing, another server on the same "
                "network may use exactly the same name and map, so the list hides yours as a copy: give it a name of its own.",
            ))
            return {"server": {**info, "gamePort": port, "queryPort": qp, "maxPlayers": info.get("max_players")}, "results": results}
        if on_ip:
            ports = ", ".join(f"{_game_port(x)} (\"{x.get('name')}\")" for x in on_ip[:5])
            results.append(_result(
                "error", f"No server on port {port}",
                f"Steam lists {'a server' if len(on_ip) == 1 else f'{len(on_ip)} servers'} on this IP, but none on port {port}: "
                f"{ports}. If one of those is yours, check that port instead. If yours is missing: {FIREWALL_TIP}",
                WIKI,
            ))
        else:
            results.append(_result(
                "error", "Steam can't see this server",
                f"Steam lists no DayZ server on {ip}, so DZSL and other launchers can't show it. {FIREWALL_TIP}",
                WIKI,
            ))
        return {"server": None, "results": results}

    results.append(_result(
        "ok", "Steam lists the server",
        f"\"{s.get('name')}\" on {s.get('map') or 'an unknown map'}, {s.get('players', 0)}/{s.get('maxPlayers', 0)} players. DZSL can find it.",
    ))

    qp = s.get("queryPort")
    info = None
    if qp:
        try:
            info = query_info(ip, qp, timeout=3)
        except (A2SError, OSError, ValueError):
            info = None
    if info:
        results.append(_result("ok", "Server answers queries", f"Query port {qp} answers in {info.get('ping', '?')} ms."))
        if info.get("password"):
            results.append(_result("warn", "Password protected", "Players need the server password to join. DZSL asks for it when you click play."))
        if s.get("modded"):
            try:
                mods = query_mods(ip, qp, timeout=3)
                results.append(_result("ok", f"{len(mods)} mods", "DZSL can read the mod list and download the mods for players."))
            except (A2SError, OSError, ValueError):
                results.append(_result("warn", "Mod list unreadable", "The server answers, but its mod list couldn't be read, so DZSL can't set up the mods automatically. Try again in a minute."))
    else:
        results.append(_result(
            "error", "Server doesn't answer queries",
            f"Query port {qp or '?'} doesn't answer, so DZSL can't read the mod list, ping or password. "
            "Open the Steam query port for UDP in your firewall and your host's control panel.",
            WIKI,
        ))

    version = s.get("version") or ""
    current = _common_version(servers)
    if current and version and _ver(version) < _ver(current):
        results.append(_result(
            "warn", "Older DayZ version than most servers",
            f"The server runs {version}, but most servers run {current}. Players on the current game join it through DayZ Experimental.",
        ))
    local = installed_version(cfg)
    if local and version and not same_major(local, version):
        results.append(_result(
            "warn", "Different version than your DayZ",
            f"The server runs {version} and your DayZ is {local}.",
        ))

    if not s.get("players"):
        results.append(_result("ok", "No players right now", "The server shows in DZSL, but the website's server list only shows servers with players online."))

    return {
        "server": {
            "name": s.get("name"), "map": s.get("map"), "players": s.get("players", 0),
            "maxPlayers": s.get("maxPlayers", 0), "version": version, "gamePort": port, "queryPort": qp,
        },
        "results": results,
    }
