import json
import os
from datetime import datetime, date, timedelta
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
FOOTBALL_API_URL = CONFIG["football"]["api_url"]
STATUS_LIST = CONFIG["football"].get("status", ["SCHEDULED"])
TIME_WINDOW = CONFIG["settings"].get("time_window", 3)


def load_football_api_token() -> Optional[str]:
    """从环境变量读取 football-data.org 的访问令牌，确保后续接口可用。"""
    load_dotenv()
    token = os.getenv("FOOTBALL_API_TOKEN")
    if not token:
        # 提示用户补充 token 以便后续调用，主流程会在没有 token 时提前退出。
        print("Please provide FOOTBALL_API_TOKEN=… in your .env so we can call football-data.org.")
    return token


def fetch_matches(token: str, status_list: list[str] = ["SCHEDULED"]) -> List[Dict[str, Any]]:
    """使用提供的 token 查询指定状态的足球比赛列表（默认只请求 SCHEDULED）。"""
    today = date.today()
    headers = {"X-Auth-Token": token}
    results = []
    for status in STATUS_LIST:
        params = {
            "status": status,
            "dateFrom": today.isoformat(),
            "dateTo": (today + timedelta(days=TIME_WINDOW)).isoformat()
            }
        competitions = os.getenv("FOOTBALL_COMPETITIONS")
        if competitions:
            # 允许通过环境变量限定需要的联赛编号（逗号分隔）
            params["competitions"] = competitions

        # 设定较短超时时间避免请求挂起
        response = requests.get(FOOTBALL_API_URL, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
        results += payload.get("matches", [])
    return results


def normalize_time(value: Optional[str]) -> str:
    """统一把 API 抓取的 UTC 时间字符串转成可读的 ISO 8601 表示。"""
    if not value:
        return ""
    try:
        # 把末尾 Z 替换为 +00:00 再交给 fromisoformat 解析
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return value


def normalize_football_match(raw: Dict[str, Any]) -> Dict[str, Any]:
    """按照推荐器的 schema 清洗足球数据，补全 id、时间和 importance 等字段。"""
    competition = raw.get("competition", {}) or {}
    home = raw.get("homeTeam", {}) or {}
    away = raw.get("awayTeam", {}) or {}

    match_id = raw.get("id")
    if match_id is None:
        # 当 API 没给 id 时，组合字段生成临时唯一键
        match_id = f"{home.get('id')}-{away.get('id')}-{raw.get('utcDate')}"

    importance_parts = []
    league_name = competition.get("name")
    stage = raw.get("stage")
    matchday = raw.get("matchday")
    if league_name:
        importance_parts.append(league_name)
    if stage and stage != "REGULAR_SEASON":
        importance_parts.append(stage)
    if matchday:
        importance_parts.append(f"Matchday {matchday}")
    importance_label = " | ".join(importance_parts) or raw.get("status", "scheduled")

    # 组装规范化后的记录，供 `matches.json` 和推荐模型使用
    return {
        "id": match_id,
        "sport": "football",
        "source": "football-data.org",
        "league": league_name or "Football",
        "teams": f"{home.get('name', 'Home')} vs {away.get('name', 'Away')}",
        "time": normalize_time(raw.get("utcDate")),
        "importance": importance_label,
        "status": raw.get("status"),
        "matchday": matchday,
        "stage": stage,
        "venue": raw.get("venue"),
        "raw": {
            "homeTeam": home.get("name"),
            "awayTeam": away.get("name"),
            "group": raw.get("group"),
        },
    }


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
    token = load_football_api_token()
    if not token:
        return

    try:
        raw_matches = fetch_matches(token)
    except requests.HTTPError as exc:
        print("Failed to fetch football fixtures:", exc)
        return

    # 清理并标准化全部 football matches
    normalized = [normalize_football_match(match) for match in raw_matches]
    all_matches = load_existing_matches()
    merged = merge_matches(all_matches, normalized)
    write_matches(merged)
    print(f"Stored {len(normalized)} football matches plus {len(all_matches) - len([m for m in all_matches if m.get('sport') == 'football'])} existing non-football entries into {MATCHES_PATH.name}.")


if __name__ == "__main__":
    main()
