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
CS2_API_URL = CONFIG["cs2"]["api_url"]


def load_cs2_api_token() -> Optional[str]:
    """从环境变量读取 CS2 比赛数据的访问令牌，确保后续接口可用。"""
    load_dotenv()
    token = os.getenv("CS2_API_TOKEN")
    if not token:
        # 提示用户补充 token 以便后续调用，主流程会在没有 token 时提前退出。
        print("Please provide CS2_API_TOKEN=… in your .env so we can call the CS2 API.")
    return token


def fetch_cs2_matches(token: str) -> List[Dict[str, Any]]:
    params = {
        "token": token
    }
    response = requests.get(CS2_API_URL, params=params, timeout=15)
    response.raise_for_status()
    res = []
    for match in response.json()[0]["matches"]:
        res.append(match.get("name"))
    return res


if __name__ == "__main__":
    print(fetch_cs2_matches(load_cs2_api_token() or ""))