import json
import os
from pathlib import Path
from typing import Any, Optional

_CONFIG_CACHE: Optional[dict] = None


def get_skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_config_path() -> Path:
    skill_root = get_skill_root()
    return skill_root / "config" / "settings.json"


def load_config(force_reload: bool = False) -> dict:
    global _CONFIG_CACHE

    if _CONFIG_CACHE is not None and not force_reload:
        return _CONFIG_CACHE

    config_path = get_config_path()

    if not config_path.exists():
        return _get_default_config()

    try:
        with config_path.open("r", encoding="utf-8") as f:
            _CONFIG_CACHE = json.load(f)
        return _CONFIG_CACHE
    except Exception:
        return _get_default_config()


def _get_default_config() -> dict:
    return {
        "version": "2.5.0",
        "scoring": {
            "short_term_weight": 0.40,
            "fundamental_weight": 0.35,
            "sentiment_weight": 0.25,
        },
        "quality_gate": {
            "score_threshold": 60,
        },
        "validation": {
            "price_min": 0.1,
            "price_max": 600.0,
        },
        "cache": {
            "intent_ttl_days": 7,
        },
        "eastmoney": {
            "daily_limit": 50,
        },
    }


def get_value(key_path: str, default: Any = None) -> Any:
    config = load_config()
    keys = key_path.split(".")

    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


def get_scoring_weights() -> dict:
    return get_value("scoring", {
        "short_term_weight": 0.40,
        "fundamental_weight": 0.35,
        "sentiment_weight": 0.25,
    })


def get_quality_gate_config() -> dict:
    return get_value("quality_gate", {
        "score_threshold": 60,
        "stop_loss_pct_min": 0.02,
        "stop_loss_pct_max": 0.15,
    })


def get_validation_config() -> dict:
    return get_value("validation", {
        "price_min": 0.1,
        "price_max": 600.0,
        "max_news_count": 30,
    })


def get_sentiment_config() -> dict:
    return get_value("sentiment", {
        "max_impact": 2.0,
        "positive_keywords": [],
        "negative_keywords": [],
    })


def get_eastmoney_config() -> dict:
    return get_value("eastmoney", {
        "daily_limit": 50,
        "cache_deduplication": True,
    })


def get_backtest_config() -> dict:
    return get_value("backtest", {
        "default_initial_capital": 100000.0,
        "commission_rate": 0.0003,
        "slippage": 0.001,
    })


def get_technical_indicators_config() -> dict:
    return get_value("technical_indicators", {
        "atr_period": 14,
        "vwap_period": 5,
        "rsi_period": 14,
    })


def get_cache_config() -> dict:
    return get_value("cache", {
        "intent_ttl_days": 7,
        "route_log_max_entries": 1000,
    })


def get_market_holidays() -> list:
    return get_value("market.a_share_holidays", [])


if __name__ == "__main__":
    print("=== 配置加载测试 ===")
    print(f"配置文件路径: {get_config_path()}")
    print(f"配置文件存在: {get_config_path().exists()}")
    print()
    print("=== 评分权重 ===")
    print(get_scoring_weights())
    print()
    print("=== 质量门禁配置 ===")
    print(get_quality_gate_config())
    print()
    print("=== 验证配置 ===")
    print(get_validation_config())
    print()
    print("=== 回测配置 ===")
    print(get_backtest_config())
