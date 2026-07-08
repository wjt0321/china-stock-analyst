import json
import logging
from pathlib import Path
from typing import Any

from desktop.storage import Storage

logger = logging.getLogger(__name__)


DEFAULT_SOURCE_PRIORITY = ["sina", "tencent", "eastmoney", "akshare"]
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
            except (json.JSONDecodeError, OSError):
                return {}
            except Exception as exc:  # pragma: no cover - defensive log
                logger.exception("Unexpected error loading defaults from %s: %s", self.defaults_path, exc)
                return {}
        return {}

    @staticmethod
    def _strip_api_key(config: dict) -> dict:
        """Return a copy of the LLM config with the API key removed.

        The API key must be supplied at runtime and is intentionally never
        persisted to the local SQLite database.
        """
        sanitized = dict(config)
        sanitized.pop("api_key", None)
        return sanitized

    def _init_defaults(self) -> None:
        if self.storage.get_setting("source_priority") is None:
            self.storage.save_setting(
                "source_priority",
                self._defaults.get("source_priority", DEFAULT_SOURCE_PRIORITY),
            )
        if self.storage.get_setting("llm_config") is None:
            llm_default = {
                **DEFAULT_LLM_CONFIG,
                **self._defaults.get("llm", {}),
            }
            self.storage.save_setting(
                "llm_config",
                self._strip_api_key(llm_default),
            )
        if self.storage.get_setting("analysis_config") is None:
            analysis = {
                **self._defaults.get("scoring", {}),
                **self._defaults.get("validation", {}),
            }
            self.storage.save_setting(
                "analysis_config",
                {**DEFAULT_ANALYSIS_CONFIG, **analysis},
            )

    def get(self, key: str, default: Any = None) -> Any:
        value = self.storage.get_setting(key, default)
        if key == "llm_config" and isinstance(value, dict):
            return self._strip_api_key(value)
        return value

    def set(self, key: str, value: Any) -> None:
        if key == "llm_config" and isinstance(value, dict):
            value = self._strip_api_key(value)
        self.storage.save_setting(key, value)

    def get_source_priority(self) -> list[str]:
        return self.storage.get_setting("source_priority", DEFAULT_SOURCE_PRIORITY)

    def get_llm_config(self) -> dict:
        config = self.storage.get_setting("llm_config", DEFAULT_LLM_CONFIG)
        return self._strip_api_key(config)

    def get_analysis_config(self) -> dict:
        return self.storage.get_setting("analysis_config", DEFAULT_ANALYSIS_CONFIG)
