import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dzsl.core.uri import validate_host
from dzsl.services.a2s import A2SError, query_info, query_mods


def measure_ping(ip, timeout=1.5):
    if not ip:
        return None
    try:
        ip = validate_host(ip)
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(max(1, int(timeout))), "--", ip],
            capture_output=True,
            text=True,
            timeout=timeout + 1,
        )
        if result.returncode != 0:
            return None
        match = re.search(r"time[=<]([\d.]+)\s*ms", result.stdout)
        if match:
            return int(float(match.group(1)))
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return None


def server_ip(server):
    return server.get("ip") or server.get("endpoint", {}).get("ip")


def _ping_server(server, ip):
    qport = server.get("queryPort")
    if qport:
        try:
            info = query_info(ip, qport, timeout=1.5)
        except A2SError:
            server["no_response"] = True
            return measure_ping(ip)
        server["no_response"] = False
        if server.get("modded") and not server.get("mods"):
            try:
                info["mods"] = query_mods(ip, qport, timeout=1.5)
            except A2SError:
                pass
        return info
    return measure_ping(ip)


def ping_servers(servers, max_workers=16, limit=80):
    targets = []
    seen = set()
    for server in servers:
        ip = server_ip(server)
        key = (ip, server.get("queryPort", 0))
        if not ip or key in seen:
            continue
        seen.add(key)
        server["_pinged"] = True
        targets.append((server, ip))
        if len(targets) >= limit:
            break

    if not targets:
        return

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_ping_server, server, ip): server for server, ip in targets}
        for future in as_completed(futures):
            server = futures[future]
            try:
                result = future.result()
            except Exception:
                result = None
            if isinstance(result, dict):
                server["ping"] = result["ping"]
                server["players"] = result["players"]
                server["queue"] = result.get("queue", 0)
                if result.get("mods"):
                    server["mods"] = result["mods"]
            else:
                server["ping"] = result
