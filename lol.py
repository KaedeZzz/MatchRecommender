import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from dotenv import load_dotenv
from config_loader import load_config

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
MATCHES_PATH = BASE_DIR / "matches.json"

CONFIG = load_config()
LOL_API_URL = CONFIG["lol"]["api_url"]
STATUS = CONFIG["lol"]["status"]
TIER = CONFIG["lol"]["tier"]


def load_lol_api_token() -> Optional[str]:
    """Load PandaScore API token from environment variables."""
    load_dotenv()
    token = os.getenv("PANDASCORE_API_TOKEN")
    if not token:
        print("Please provide PANDASCORE_API_TOKEN=*** in your .env so we can call the LoL API.")
    return token


def build_lol_api_url(verbose: bool = False) -> str:
    """Build the PandaScore LoL API URL with required query params."""
    url = LOL_API_URL + "/{}?range[tier]={}".format(STATUS, ",".join(TIER))
    if verbose:
        print("LoL API URL:", url)
    return url


def fetch_lol_matches(token: str) -> List[Dict[str, Any]]:
    params = {"token": token}
    url = build_lol_api_url()
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    match_list: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for tournament in response.json():
        league = tournament.get("league", {}).get("name")
        serie = tournament.get("serie", {}).get("name")
        name = str(league or "") + " " + str(serie or "")
        for match in tournament.get("matches", []):
            if "TBD" in match.get("name", ""):
                continue

            start = match.get("begin_at") or match.get("scheduled_at")
            match_time = None
            if start:
                try:
                    match_time = datetime.fromisoformat(start.replace("Z", "+00:00"))
                except ValueError:
                    match_time = None
            if match_time and match_time < now:
                continue

            match["tournament"] = name.strip() or "LoL Tournament"
            match_list.append(match)
    return match_list


def normalize_time(value: Optional[str]) -> str:
    """Convert PandaScore UTC timestamps to ISO 8601 strings."""
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return value


def get_team_names(raw: Dict[str, Any]) -> List[str]:
    """Extract readable team names from the PandaScore opponents payload."""
    opponents = raw.get("opponents") or []
    names: List[str] = []
    for opponent_record in opponents:
        opponent = opponent_record.get("opponent")
        if not opponent:
            continue
        name = opponent.get("name")
        if name:
            names.append(name)
    return names


def normalize_lol_match(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a single LoL match into the shared match schema."""
    match_id = raw.get("id") or f"{raw.get('name', 'lol')}-{raw.get('begin_at')}"

    team_names = get_team_names(raw)
    teams = " vs ".join(team_names) or raw.get("name") or "LoL Match"

    tournament = raw.get("tournament") or "Unknown Tournament"

    start_time = raw.get("begin_at") or raw.get("scheduled_at")
    stage = raw.get("round") or raw.get("phase")

    return {
        "id": match_id,
        "sport": "lol",
        "source": "pandascore.co",
        "tournament": tournament,
        "teams": teams,
        "time": normalize_time(start_time),
        "importance": "tier-" + TIER[-1] if TIER else "unknown",
        "status": raw.get("status"),
        "stage": stage,
    }


def normalize_lol_matches(raw_matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize a list of LoL matches returned by PandaScore into the unified match schema."""
    normalized: List[Dict[str, Any]] = []
    for match in raw_matches:
        if not match:
            continue
        normalized.append(normalize_lol_match(match))
    return normalized


def load_existing_matches() -> List[Dict[str, Any]]:
    if not MATCHES_PATH.exists():
        return []
    try:
        with MATCHES_PATH.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"Warning: {MATCHES_PATH} contained invalid JSON ({exc}), overwriting.")
    return []


def merge_matches(existing: List[Dict[str, Any]], new: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Replace LoL entries with freshly fetched data while keeping other sports."""
    new_keys: Set[Tuple[Any, Any]] = {(item["sport"], item["id"]) for item in new}
    preserved = [item for item in existing if (item.get("sport"), item.get("id")) not in new_keys]
    combined = preserved + new
    return sorted(combined, key=lambda entry: entry.get("time") or "")


def write_matches(matches: List[Dict[str, Any]]):
    MATCHES_PATH.write_text(json.dumps(matches, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    token = load_lol_api_token()
    if not token:
        return

    try:
        raw_matches = fetch_lol_matches(token)
    except requests.HTTPError as exc:
        print("Failed to fetch LoL matches:", exc)
        return

    normalized = [normalize_lol_match(match) for match in raw_matches]
    all_matches = load_existing_matches()
    merged = merge_matches(all_matches, normalized)
    write_matches(merged)
    print(
        f"Stored {len(normalized)} LoL matches plus "
        f"{len(all_matches) - len([m for m in all_matches if m.get('sport') == 'lol'])} "
        f"existing non-LoL entries into {MATCHES_PATH.name}."
    )


if __name__ == "__main__":
    main()
