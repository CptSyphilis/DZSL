#!/bin/bash
set -euo pipefail

INSTALL_DIR="${DZSL_INSTALL_DIR:-$HOME/DZSL}"
CONFIG_DIR="$HOME/.config/dzsl"
DESKTOP="$HOME/.local/share/applications/dzsl.desktop"

_resolve() { readlink -f "$1" 2>/dev/null || echo "$1"; }
TARGET="$(_resolve "$INSTALL_DIR")"

if [ "$TARGET" = "$(_resolve "/")" ] || [ "$TARGET" = "$(_resolve "$HOME")" ]; then
    echo "Error: unsafe install path ($INSTALL_DIR)"
    exit 1
fi

echo "DZSL Uninstaller"
echo ""
echo "Will remove:"
echo "  $INSTALL_DIR"
echo "  $CONFIG_DIR"
echo "  $DESKTOP"
echo ""

read -p "Uninstall DZSL? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""

if [ -f "$DESKTOP" ]; then
    rm "$DESKTOP"
    echo "Removed desktop shortcut."
else
    echo "No desktop shortcut found."
fi

if [ -d "$CONFIG_DIR" ]; then
    rm -rf "$CONFIG_DIR"
    echo "Removed $CONFIG_DIR"
else
    echo "No config at $CONFIG_DIR"
fi

if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo "Removed $INSTALL_DIR"
else
    echo "No install at $INSTALL_DIR"
fi

echo ""
echo "Done."