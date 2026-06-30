from dzsl.http import get_json, post_form_json


PUBLISHED_FILES_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
PLAYER_SUMMARIES_URL = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"


def _workshop_ids(values):
    ids = []
    for value in values or []:
        mod_id = str(value).strip()
        if not mod_id.isdigit():
            raise ValueError(f"Invalid Workshop ID: {mod_id}")
        ids.append(mod_id)
    return ids


def published_file_details(mod_ids, timeout=30):
    ids = _workshop_ids(mod_ids)
    details = []
    for start in range(0, len(ids), 100):
        batch = ids[start:start + 100]
        payload = {"itemcount": len(batch)}
        for index, mod_id in enumerate(batch):
            payload[f"publishedfileids[{index}]"] = mod_id
        items = post_form_json(PUBLISHED_FILES_URL, payload, timeout=timeout).get(
            "response", {}
        ).get("publishedfiledetails", [])
        if not isinstance(items, list):
            raise ValueError("Steam returned invalid Workshop details")
        details.extend(items)
    return details


def player_summaries(steam_ids, api_key, timeout=30):
    ids = _workshop_ids(steam_ids)
    players = []
    for start in range(0, len(ids), 100):
        batch = ids[start:start + 100]
        payload = get_json(
            PLAYER_SUMMARIES_URL,
            params={"key": api_key, "steamids": ",".join(batch)},
            timeout=timeout,
        )
        batch_players = payload.get("response", {}).get("players", [])
        if not isinstance(batch_players, list):
            raise ValueError("Steam returned invalid player summaries")
        players.extend(batch_players)
    return players
