from pathlib import Path

import pytest

from desktop.config_manager import ConfigManager
from desktop.storage import Storage


def test_source_priority_default(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.init_schema()
    cm = ConfigManager(storage, defaults_path=Path("nonexistent.json"))
    priority = cm.get_source_priority()
    assert priority[0] == "eastmoney"


def test_llm_config_default(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.init_schema()
    cm = ConfigManager(storage, defaults_path=Path("nonexistent.json"))
    config = cm.get_llm_config()
    assert config["enabled"] is False
    assert config["provider"] == "deepseek"


def test_analysis_config_default(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.init_schema()
    cm = ConfigManager(storage, defaults_path=Path("nonexistent.json"))
    config = cm.get_analysis_config()
    assert config["short_term_weight"] == 0.40
    assert config["fundamental_weight"] == 0.35
    assert config["sentiment_weight"] == 0.25


def test_get_and_set(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.init_schema()
    cm = ConfigManager(storage, defaults_path=Path("nonexistent.json"))
    assert cm.get("custom_key", "default") == "default"
    cm.set("custom_key", "value")
    assert cm.get("custom_key") == "value"


def test_file_defaults_override(tmp_path):
    defaults = tmp_path / "defaults.json"
    defaults.write_text(
        '{"source_priority": ["sina", "eastmoney"], "llm": {"enabled": true}}',
        encoding="utf-8",
    )
    storage = Storage(tmp_path / "test.db")
    storage.init_schema()
    cm = ConfigManager(storage, defaults_path=defaults)
    assert cm.get_source_priority() == ["sina", "eastmoney"]
    assert cm.get_llm_config()["enabled"] is True


def test_init_does_not_overwrite_existing_settings(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.init_schema()
    storage.save_setting("source_priority", ["custom"])
    storage.save_setting("llm_config", {"enabled": True})
    storage.save_setting("analysis_config", {"short_term_weight": 0.99})

    defaults = tmp_path / "defaults.json"
    defaults.write_text(
        '{"source_priority": ["sina", "eastmoney"], "llm": {"enabled": false}}',
        encoding="utf-8",
    )
    cm = ConfigManager(storage, defaults_path=defaults)

    assert cm.get_source_priority() == ["custom"]
    assert cm.get_llm_config()["enabled"] is True
    assert cm.get_analysis_config()["short_term_weight"] == 0.99
