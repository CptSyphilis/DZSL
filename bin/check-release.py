#!/usr/bin/env python3
import re
import sys
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parent.parent


def _match(path, pattern):
    text = path.read_text(encoding="utf-8")
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        raise ValueError(f"Version not found in {path.relative_to(ROOT)}")
    return match.group(1)


def release_versions():
    code = _match(
        ROOT / "dzsl/core/constants.py",
        r'^VERSION\s*=\s*"([^"]+)"',
    )
    project = _match(
        ROOT / "pyproject.toml",
        r'^version\s*=\s*"([^"]+)"',
    )
    metadata = ElementTree.parse(
        ROOT / "packaging/flatpak/com.dayzlinux.dzsl.metainfo.xml"
    ).getroot()
    release = metadata.find("./releases/release")
    if release is None or not release.get("version"):
        raise ValueError("Latest Flatpak release version not found")
    return {
        "application": code,
        "project": project,
        "flatpak": release.get("version"),
    }


def main():
    versions = release_versions()
    if len(set(versions.values())) != 1:
        for source, version in versions.items():
            print(f"{source}: {version}", file=sys.stderr)
        raise SystemExit("Release versions do not match")
    print(f"Release metadata OK: {versions['application']}")


if __name__ == "__main__":
    main()
