import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from dotenv import load_dotenv
from config_loader import load_config

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
MATCHES_PATH = BASE_DIR / "matches.json"
# football-data.org 提供的比赛列表接口，params 决定具体筛选

CONFIG = load_config()
CS2_API_URL = CONFIG["cs2"]["api_url"]
STATUS = CONFIG["cs2"]["status"]
TIER = CONFIG["cs2"]["tier"]


def load_cs2_api_token() -> Optional[str]:
    """从环境变量读取 CS2 比赛数据的访问令牌，确保后续接口可用。"""
    load_dotenv()
    token = os.getenv("CS2_API_TOKEN")
    if not token:
        # 提示用户补充 token 以便后续调用，主流程会在没有 token 时提前退出。
        print("Please provide CS2_API_TOKEN=… in your .env so we can call the CS2 API.")
    return token


def build_cs2_api_url(verbose: bool = False) -> str:
    """构建 CS2 比赛数据的 API URL，包含必要的查询参数。"""
    url = CS2_API_URL + "/{}?range[tier]={}".format(STATUS, ",".join(TIER))
    if verbose:
        print("CS2 API URL:", url)
    return url


def fetch_cs2_matches(token: str) -> List[Dict[str, Any]]:
    params = {
        "token": token
    }
    url = build_cs2_api_url()
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    match_list = []
    tournament_list = response.json()
    for tournament in response.json():
        league = tournament.get("league", {}).get("name")
        serie = tournament.get("serie", {}).get("name")
        name = str(league or "") + " " + str(serie or "")
        for match in tournament.get("matches", []):
            if not "TBD" in match.get("name", ""):
                match["tournament"] = name
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


def normalize_cs2_match(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a single CS2 match into the shared match schema."""
    match_id = raw.get("id") or f"{raw.get('name', 'cs2')}-{raw.get('begin_at')}"

    team_names = get_team_names(raw)
    teams = " vs ".join(team_names) or raw.get("name") or "CS2 Match"

    tournament = raw.get("tournament") or "Unknown Tournament"

    start_time = raw.get("begin_at") or raw.get("scheduled_at")
    stage = raw.get("round") or raw.get("phase")

    return {
        "id": match_id,
        "sport": "cs2",
        "source": "pandascore.co",
        "tournament": tournament,
        "teams": teams,
        "time": normalize_time(start_time),
        "importance": "tier-" + TIER[-1] if TIER else "unknown",
        "status": raw.get("status"),
        "stage": stage,
    }


def normalize_cs2_matches(raw_matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize a list of CS2 matches returned by PandaScore into the unified match schema.
    Empty entries are skipped.
    """
    normalized: List[Dict[str, Any]] = []
    for match in raw_matches:
        if not match:
            continue
        normalized.append(normalize_cs2_match(match))
    return normalized


def load_existing_matches() -> List[Dict[str, Any]]:
    if not MATCHES_PATH.exists():
        return []
    try:
        with MATCHES_PATH.open("r", encoding="utf-8") as fh:
            # 继续使用已经存在的比赛列表（包括其他运动）
            return json.load(fh)
    except json.JSONDecodeError as exc:
        # 如果文件被破坏，通知并准备重写
        print(f"Warning: {MATCHES_PATH} contained invalid JSON ({exc}), overwriting.")
    return []


def merge_matches(existing: List[Dict[str, Any]], new: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """将新抓取的足球场次替换老数据，同时保留其他运动的条目。"""
    new_keys: Set[Tuple[Any, Any]] = {(item["sport"], item["id"]) for item in new}
    # 过滤出不属于本次 football 更新的记录，避免重复覆盖
    preserved = [item for item in existing if (item.get("sport"), item.get("id")) not in new_keys]
    combined = preserved + new
    # 按 ISO 时间排序，方便推荐器按照时间线输出
    return sorted(combined, key=lambda entry: entry.get("time") or "")


def write_matches(matches: List[Dict[str, Any]]):
    # 将合并后的结构化列表写回文件供推荐脚本直接读取
    MATCHES_PATH.write_text(json.dumps(matches, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    token = load_cs2_api_token()
    if not token:
        return

    try:
        raw_matches = fetch_cs2_matches(token)
    except requests.HTTPError as exc:
        print("Failed to fetch CS2 matches:", exc)
        return

    # 清理并标准化全部 CS2 matches
    normalized = [normalize_cs2_match(match) for match in raw_matches]
    all_matches = load_existing_matches()
    merged = merge_matches(all_matches, normalized)
    write_matches(merged)
    print(f"Stored {len(normalized)} CS2 matches plus {len(all_matches) - len([m for m in all_matches if m.get('sport') == 'cs2'])} existing non-CS2 entries into {MATCHES_PATH.name}.")


if __name__ == "__main__":
    main()
    # raw_matches = fetch_cs2_matches(load_cs2_api_token() or "")
    # normalized_matches = normalize_cs2_matches(raw_matches)
    # print(normalized_matches)
