# match_recommender.py
# 一个最小可跑的「体育+电竞比赛推荐」脚本

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from openai import OpenAI

# 1. 读取 .env 里的 OPENAI_API_KEY
load_dotenv()

client: Optional[OpenAI] = None  # 延迟创建，先检查是否有 API Key


# ===== 你可以按自己喜好改的部分 =====

# 用户配置路径
USER_PROFILE_PATH = Path(__file__).with_name("user_profile.txt")
# 赛程来源文件
MATCHES_PATH = Path(__file__).with_name("matches.json")


# ===== 核心函数：调用 OpenAI 做推荐 =====


def get_client() -> Optional[OpenAI]:
    """
    运行前先检查是否设置了 OPENAI_API_KEY，避免无 Key 时再请求才报错。
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
        print("未找到 user_profile.txt，请先填写兴趣偏好。")
        return ""

    try:
        profile = path.read_text(encoding="utf-8")
    except Exception as e:
        print("读取 user_profile.txt 失败，请检查文件编码或权限。错误：", repr(e))
        return ""

    profile = profile.strip()
    if not profile:
        print("user_profile.txt 为空，请写入你想要的兴趣描述。")
        return ""

    return profile


def load_matches(path: Path = MATCHES_PATH) -> List[Dict[str, Any]]:
    """
    读取 `matches.json` 中的比赛列表，失败时返回空数组（需要用户自行生成）。
    """
    if not path.exists():
        print(f"{path.name} 不存在，请先生成或同步比赛数据。")
        return []

    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except Exception as exc:
        print(f"读取 {path.name} 失败，请确认 JSON 格式正确。错误：{exc}")
        return []

    if not isinstance(data, list):
        print(f"{path.name} 内容不是数组结构，请修复文件。")
        return []

    return data


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
   - score: 推荐分数（0-100 的整数，越高越推荐）
   - reason: 中文推荐理由，1-2 句话。
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
    if api_client is None:
        return []

    prompt = build_prompt(user_profile, matches)

    try:
        response = api_client.responses.create(
            model="gpt-5-nano",  # 便宜好用的通用模型，可按需更换:contentReference[oaicite:1]{index=1}
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
            # 默认 text 输出即可，通过 SDK 的 output_text 取完整文本:contentReference[oaicite:2]{index=2}
        )
    except Exception as e:
        print("调用 OpenAI API 出错：", repr(e))
        return []

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


def print_recommendations(recommendations: List[Dict[str, Any]],
                          matches: List[Dict[str, Any]]):
    """
    把推荐结果以比较好看的方式打印出来
    """
    if not recommendations:
        print("没有推荐结果。")
        return

    # 按 score 从高到低排一下（模型一般已经排好，这里再保险一下）
    recommendations = sorted(
        recommendations,
        key=lambda r: r.get("score", 0),
        reverse=True
    )

    print("\n================= 今日推荐比赛 =================\n")
    for idx, rec in enumerate(recommendations, start=1):
        match = find_match_by_id(rec.get("id"), matches) # type: ignore
        if not match:
            continue

        score = rec.get("score", 0)
        reason = rec.get("reason", "")

        print(f"{idx}. [{score:>3} 分] {match.get('teams')}")

        extra = []
        if match.get("league"):
            extra.append(match["league"])
        if match.get("sport"):
            extra.append(match["sport"])
        if match.get("game"):
            extra.append(match["game"])
        extra_str = " | ".join(extra)

        print(f"   时间: {match.get('time', '未知时间')}")
        if extra_str:
            print(f"   联赛/项目: {extra_str}")
        if match.get("importance"):
            print(f"   重要性: {match['importance']}")
        print(f"   推荐理由: {reason}")
        print()


def main():
    print("正在生成今日比赛推荐...\n")

    user_profile = load_user_profile()
    matches = load_matches()

    recommendations = call_model_for_recommendations(
        user_profile=user_profile,
        matches=matches
    )

    print_recommendations(recommendations, matches)


if __name__ == "__main__":
    main()
