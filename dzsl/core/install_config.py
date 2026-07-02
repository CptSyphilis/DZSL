import json
import os
import sys
import tempfile


DEFAULTS = {
    "steam_root": "",
    "mods_dir": "",
    "profile_name": "",
    "extra_args": "",
    "extra_mods": "",
    "no_splash": True,
    "no_pause": True,
    "no_benchmark": False,
    "window_mode": False,
    "script_debug": False,
    "skip_battleye": False,
    "close_on_launch": True,
}


def merge_install_config(existing, detected_steam_root):
    existing = existing if isinstance(existing, dict) else {}
    merged = {**DEFAULTS, **existing}
    merged.pop("launcher_path", None)
    if not merged.get("steam_root"):
        merged["steam_root"] = detected_steam_root
    return merged


def update_install_config(path, detected_steam_root):
    existing = {}
    try:
        with open(path, encoding="utf-8") as handle:
            existing = json.load(handle)
    except (OSError, ValueError):
        pass

    data = merge_install_config(existing, detected_steam_root)
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".dzsl-install-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return data


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: install_config.py CONFIG_PATH STEAM_ROOT")
    update_install_config(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
