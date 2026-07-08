import json
from pathlib import Path
from typing import Any

from desktop.storage import Storage


DEFAULT_SOURCE_PRIORITY = ["eastmoney", "sina", "ths", "tencent", "akshare"]
DEFAULT_LLM_CONFIG = {
    "enabled": False,
    "provider": "deepseek",
    "base_url": "https://api.deepseek.com/v1",
    "api_key": "",
    "model": "deepseek-chat",
}
DEFAULT_ANALYSIS_CONFIG = {
    "short_term_weight": 0.40,
    "fundamental_weight": 0.35,
    "sentiment_weight": 0.25,
    "price_conflict_threshold": 0.01,
    "change_conflict_threshold": 0.012,
    "fund_flow_conflict_threshold": 0.35,
}


class ConfigManager:
    def __init__(self, storage: Storage, defaults_path: Path):
        self.storage = storage
        self.defaults_path = Path(defaults_path)
        self._defaults = self._load_file_defaults()
        self._init_defaults()

    def _load_file_defaults(self) -> dict:
        if self.defaults_path.exists():
            try:
                with self.defaults_path.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _init_defaults(self) -> None:
        if self.storage.get_setting("source_priority") is None:
            self.storage.save_setting(
                "source_priority",
                self._defaults.get("source_priority", DEFAULT_SOURCE_PRIORITY),
            )
        if self.storage.get_setting("llm_config") is None:
            self.storage.save_setting(
                "llm_config",
                self._defaults.get("llm", DEFAULT_LLM_CONFIG),
            )
        if self.storage.get_setting("analysis_config") is None:
            analysis = self._defaults.get("scoring", {})
            analysis.update(self._defaults.get("validation", {}))
            self.storage.save_setting(
                "analysis_config",
                {**DEFAULT_ANALYSIS_CONFIG, **analysis},
            )

    def get(self, key: str, default: Any = None) -> Any:
        return self.storage.get_setting(key, default)

    def set(self, key: str, value: Any) -> None:
        self.storage.save_setting(key, value)

    def get_source_priority(self) -> list[str]:
        return self.storage.get_setting("source_priority", DEFAULT_SOURCE_PRIORITY)

    def get_llm_config(self) -> dict:
        return self.storage.get_setting("llm_config", DEFAULT_LLM_CONFIG)

    def get_analysis_config(self) -> dict:
        return self.storage.get_setting("analysis_config", DEFAULT_ANALYSIS_CONFIG)
