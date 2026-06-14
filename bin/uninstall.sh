#!/bin/bash
# DZSL Uninstaller

echo "╔══════════════════════════════════╗"
echo "║   DZSL Uninstaller               ║"
echo "╚══════════════════════════════════╝"
echo ""

# Remove desktop entry
if [ -f "$HOME/.local/share/applications/dzsl.desktop" ]; then
    rm "$HOME/.local/share/applications/dzsl.desktop"
    echo "Removed desktop shortcut."
fi

# Ask about config/data
read -p "Remove saved favorites and settings? [y/N] " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
    rm -rf "$HOME/.config/dzsl"
    echo "Removed config and favorites."
else
    echo "Kept config and favorites at ~/.config/dzsl/"
fi

echo ""
echo "DZSL uninstalled. You can delete the DZSL folder manually."
echo ""
