# match_recommender.py
# 一个最小可跑的「体育+电竞比赛推荐」脚本

import os
import json
from time import perf_counter
from pathlib import Path
from typing import List, Dict, Any, Optional

from config_loader import load_config

from dotenv import load_dotenv
from openai import OpenAI
from football import fetch_football_matches, load_allowed_competitions, load_football_api_token, normalize_football_match
from cs2 import fetch_cs2_matches, load_cs2_api_token, normalize_cs2_match
from lol import fetch_lol_matches, load_lol_api_token, normalize_lol_match

from time_utils import convert_utc_to_local_time


client: Optional[OpenAI] = None  # 延迟创建，先检查是否有 API Key

BASE_DIR = Path(__file__).resolve().parent
USER_PROFILE_PATH = BASE_DIR / "user_profile.txt"


load_dotenv()  # 读取 .env 里的 OPENAI_API_KEY
CONFIG = load_config()
MODEL = CONFIG["settings"].get("model", "gpt-5-nano")
DEBUG_MODE = CONFIG["settings"].get("debug_mode", False)


# ===== 核心函数：调用 OpenAI 做推荐 =====


def get_client() -> Optional[OpenAI]:
    """
    运行前先检查是否设置了 OPENAI_API_KEY，避免无 Key 时再请求才报错。
    如果有 Key，则创建并返回 OpenAI 客户端实例。
    """
    global client

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("未检测到 OPENAI_API_KEY 环境变量，请在项目根目录创建 .env 并写入 OPENAI_API_KEY=sk-***")
        return None

    if client is None:
        client = OpenAI(api_key=api_key)
    return client


def load_user_profile(path: Path = USER_PROFILE_PATH) -> str:
    """
    从配置文件读取用户兴趣，缺失或异常时返回空字符串（需要用户补全）。
    """
    if not path.exists():
        print("未找到 user_profile.txt，请先创建用户偏好文件。")
        return ""

    try:
        profile = path.read_text(encoding="utf-8")
    except Exception as e:
        print("读取 user_profile.txt 失败，请检查文件编码或权限。错误：", repr(e))
        return ""

    profile = profile.strip()  # 去掉首尾空白
    if not profile:
        print("user_profile.txt 为空，请写入你想要的兴趣描述。")
        return ""

    return profile


def build_prompt(user_profile: str, matches: List[Dict[str, Any]]) -> str:
    """
    把用户兴趣 + 比赛列表拼成一个 prompt 给模型看
    """
    return f"""
你是一个资深体育+电竞赛事推荐编辑，需要根据用户兴趣对比赛进行打分排序并给出推荐理由。

【用户兴趣】
{user_profile}

【待选比赛列表（JSON 数组）】
{json.dumps(matches, ensure_ascii=False)}

请根据用户兴趣为每场比赛打分并排序，要求：
1. 返回一个 JSON 对象，字段为 "recommendations"（数组）。
2. recommendations 数组中每个元素包含字段：
   - id: 比赛 id（整数）
   - teams：比赛双方的队名，格式如 "队伍A vs 队伍B"，不要包括别的信息。如果不是电竞比赛，则把队名全部翻译成中文。如果是电竞比赛，则把队名的缩写扩展成队伍全名。
   - score: 推荐分数（0-100 的整数，越高越推荐）
   - reason: 推荐理由（简短说明为什么推荐这场比赛，围绕用户兴趣展开）
3. 只输出 JSON，不要任何额外解释、文字或代码块标记。
"""


def call_model_for_recommendations(user_profile: str,
                                   matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    调用 OpenAI Responses API，请模型给出推荐结果（结构化 JSON）
    """
    if not matches:
        print("没有待选比赛。")
        return []

    api_client = get_client()
    if api_client is None:  # 没有生成客户端实体
        return []

    prompt = build_prompt(user_profile, matches)

    start = perf_counter()
    try:
        response = api_client.responses.create(
            model=MODEL,
            input=[
                {
                    "role": "system",
                    "content": "你是一个专业的体育+电竞赛事推荐助手，会输出严格的 JSON。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            # 默认 text 输出即可，通过 SDK 的 output_text 取完整文本
        )
    except Exception as e:
        print("调用 OpenAI API 出错：", repr(e))
        return []

    if DEBUG_MODE:
        elapsed = perf_counter() - start
        print(f"[debug] OpenAI API call took {elapsed:.2f}s")

    # SDK 会帮你把所有 text 输出拼在一起放到 output_text 里
    raw_text = getattr(response, "output_text", None)
    if not raw_text:
        print("模型没有返回文本输出，原始响应：", response)
        return []

    # 尝试解析 JSON
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        print("解析 JSON 失败，模型原始输出如下：")
        print(raw_text)
        return []

    recs = data.get("recommendations", [])
    if not isinstance(recs, list):
        print("返回的 JSON 中没有有效的 recommendations 数组。原始数据：", data)
        return []

    return recs


def find_match_by_id(match_id: int, matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """辅助函数：通过 id 找到对应比赛信息"""
    for m in matches:
        if m.get("id") == match_id:
            return m
    return {}


def print_recommendations(recommendations: List[Dict[str, Any]], matches: List[Dict[str, Any]],
                          count: int = 10) -> None:
    """
    打印个性化赛事推荐结果（适配本机时区展示时间）
    :param recommendations: AI生成的推荐列表（含score/reason/id）
    :param matches: 标准化后的赛事数据列表
    :param count: 展示的推荐数量，默认前10
    """
    # 1. 按推荐分数降序排序，限制展示数量
    sorted_recs = sorted(recommendations, key=lambda x: x["score"], reverse=True)[:count]
    if DEBUG_MODE:
        print(f"已推荐{len(sorted_recs)}场比赛。")

    # 2. 打印标题
    print("\n=== 个性化赛事推荐===")

    # 3. 遍历推荐结果，逐个格式化打印
    for idx, rec in enumerate(sorted_recs, 1):
        # 3.1 根据赛事ID匹配原始赛事数据（处理无匹配的异常）

        try:
            match = next(m for m in matches if m["id"] == rec["id"])
        except StopIteration:
            print(f"{idx}. 推荐分数：{rec['score']}分 | 赛事数据不存在（ID：{rec['id']}）")
            continue

        # 3.2 将UTC时间转为本机时区时间
        original_utc_time = match.get("time", "未知时间")  # 防KeyError
        local_time = convert_utc_to_local_time(original_utc_time)

        # 3.3 格式化打印
        score = rec["score"]  # 推荐分数
        teams_str = match.get("teams", "未知对阵")  # 完整对阵字符串（含阶段）
        local_time = convert_utc_to_local_time(match.get("time", "未知时间"))  # 转换后的时间
        sport = match.get("sport", "未知项目")  # 项目/运动类型
        league = match.get("league", sport)  # 联赛（无则用项目填充）
        importance = match.get("importance", "未知重要性")  # 重要性
        reason = rec.get("reason", "无推荐理由")  # 推荐理由

        # 2. 按指定格式拼接输出（严格匹配示例）
        print(f"{idx}. [ {score} 分] {teams_str}")
        print(f"   时间: {local_time}（{sport} | 本机时区）")
        print(f"   联赛/项目: {league}")
        print(f"   重要性: {importance}")
        print(f"   推荐理由: {reason}")
        print()


def main():
    print("正在生成今日比赛推荐...\n")

    user_profile = load_user_profile()

    # 启动时先拉取 API，再生成推荐
    matches: List[Dict[str, Any]] = []

    football_token = load_football_api_token()
    football_matches = []
    if football_token:
        try:
            raw_football_matches = fetch_football_matches(football_token)
            allowed_competitions = load_allowed_competitions()
            if allowed_competitions:
                raw_football_matches = [
                    match
                    for match in raw_football_matches
                    if (match.get("competition") or {}).get("name") in allowed_competitions
                ]
            football_matches = [normalize_football_match(m) for m in raw_football_matches]
            print(f"已从 API 获取 {len(football_matches)} 场足球比赛。")
        except Exception as exc:
            print("获取比赛列表失败：", repr(exc))

    cs2_token = load_cs2_api_token()
    cs2_matches = []
    if cs2_token:
        try:
            raw_cs2_matches = fetch_cs2_matches(cs2_token)
            cs2_matches = [normalize_cs2_match(m) for m in raw_cs2_matches]
            print(f"已从 API 获取 {len(cs2_matches)} 场 CS2 比赛。")
        except Exception as exc:
            print("获取比赛列表失败：", repr(exc))

    lol_token = load_lol_api_token()
    lol_matches = []
    if lol_token:
        try:
            raw_lol_matches = fetch_lol_matches(lol_token)
            lol_matches = [normalize_lol_match(m) for m in raw_lol_matches]
            print(f"已从 API 获取 {len(lol_matches)} 场 LoL 比赛。")
        except Exception as exc:
            print("获取比赛列表失败：", repr(exc))
    
    matches = football_matches + cs2_matches + lol_matches

    recommendations = call_model_for_recommendations(
        user_profile=user_profile,
        matches=matches
    )

    print_recommendations(recommendations, matches)




if __name__ == "__main__":
    main()
