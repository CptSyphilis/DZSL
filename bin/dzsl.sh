#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    echo "DZSL: no display session found. Open a terminal on your desktop and try again." >&2
    exit 1
fi

if [[ "${DZSL_USE_WAYLAND:-}" != "1" ]]; then
    if [[ "${DZSL_USE_X11:-}" == "1" || "${XDG_SESSION_TYPE:-}" == "wayland" || -n "${WAYLAND_DISPLAY:-}" ]]; then
        export GDK_BACKEND=x11
    fi
fi

exec python3 main.py "$@"
