import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dzsl.core.uri import validate_host


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


def ping_servers(servers, max_workers=16, limit=80):
    targets = []
    seen = set()
    for server in servers:
        ip = server_ip(server)
        if not ip or ip in seen:
            continue
        seen.add(ip)
        targets.append((server, ip))
        if len(targets) >= limit:
            break

    if not targets:
        return

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(measure_ping, ip): server for server, ip in targets}
        for future in as_completed(futures):
            server = futures[future]
            try:
                server["ping"] = future.result()
            except Exception:
                server["ping"] = None
