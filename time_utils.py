import pytz
from datetime import datetime
from tzlocal import get_localzone
from pytz import UnknownTimeZoneError

# 提前检测1次本机时区（避免重复检测）
def _get_system_timezone_once() -> str:
    """仅初始化1次本机时区，缓存结果"""
    try:
        local_tz = get_localzone()
        tz_str = str(local_tz)
        pytz.timezone(tz_str)  # 校验有效性

        return tz_str
    except Exception as e:
        print(f"时区检测失败：{e}，默认UTC")
        return "UTC"

# 缓存时区结果（全局变量，仅加载1次）
LOCAL_TIMEZONE_STR = _get_system_timezone_once()
LOCAL_TIMEZONE = pytz.timezone(LOCAL_TIMEZONE_STR)

def convert_utc_to_local_time(
    utc_time_str: str,
    output_format: str = "%Y-%m-%d %H:%M"
) -> str:
    """
    转换UTC时间到本机时区（兼容：带时区的datetime + 朴素datetime）
    解决「Not naive datetime」错误
    """
    try:
        # 步骤1：解析时间字符串（兼容Z和+00:00格式）
        if utc_time_str.endswith("Z"):
            # 处理 Z 结尾的格式（如 2025-12-13T16:09:22Z）
            utc_dt = datetime.fromisoformat(utc_time_str.replace("Z", "+00:00"))
        else:
            # 处理带偏移的格式（如 2025-12-13T16:09:22+00:00）
            utc_dt = datetime.fromisoformat(utc_time_str)

        # 步骤2：判断是否已有时区信息，避免重复绑定
        if utc_dt.tzinfo is None:
            # 无时区：手动绑定UTC
            utc_dt = pytz.UTC.localize(utc_dt)
        else:
            # 已有时区：转换为UTC（兼容非UTC的情况，如+08:00）
            utc_dt = utc_dt.astimezone(pytz.UTC)

        # 步骤3：转换为本机时区（自动适配夏令时）
        local_dt = utc_dt.astimezone(LOCAL_TIMEZONE)

        # 步骤4：格式化输出
        return local_dt.strftime(output_format)

    except Exception as e:
        print(f"时间转换失败：{e}，使用原始UTC时间")
        return utc_time_str

# 兼容时间戳的版本（可选）
def convert_timestamp_to_local_time(timestamp: int, output_format: str = "%Y-%m-%d %H:%M (%Z%z)") -> str:
    try:
        utc_dt = pytz.UTC.localize(datetime.utcfromtimestamp(timestamp))
        local_dt = utc_dt.astimezone(LOCAL_TIMEZONE)
        return local_dt.strftime(output_format)
    except Exception as e:
        print(f"时间戳转换失败：{e}，使用原始时间戳")
        return str(timestamp)