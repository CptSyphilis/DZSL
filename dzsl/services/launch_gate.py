from dzsl.core.config import is_steam_ready, mod_installed, mod_subscribed


def launch_block_reason(cfg, mod_ids, ready_check=None, installed_check=None, subscribed_check=None):
    ready_check = ready_check or is_steam_ready
    installed_check = installed_check or mod_installed
    subscribed_check = subscribed_check or mod_subscribed
    ids = list(dict.fromkeys(str(mod_id) for mod_id in mod_ids or []))
    if not ready_check():
        return "Steam is not ready"
    missing = [mid for mid in ids if not subscribed_check(cfg, mid)]
    if missing:
        return "Required mods are not subscribed: " + ", ".join(missing)
    incomplete = [mid for mid in ids if not installed_check(cfg, mid)]
    if incomplete:
        return "Required mods are not fully downloaded: " + ", ".join(incomplete)
    return ""
