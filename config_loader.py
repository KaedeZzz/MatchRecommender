import json
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"


def load_config() -> Dict[str, Any]:
    """
    Load the configuration from config.json and merge any overrides on top of defaults.
    """
    if not CONFIG_PATH.exists():
        print("config.json is missing; skipping configuration load.")
        return {}

    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        print("Failed to parse config.json:", exc)
        return {}

    merged: Dict[str, Any] = {}
    for key, default_section in raw.items():
        section = default_section.copy()
        incoming = raw.get(key)
        if isinstance(incoming, dict):
            section.update(incoming)
        merged[key] = section
    return merged


CONFIG = load_config()
