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
        "version": "2.6.0",
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
            "intent_ttl_seconds": 300,
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
        "emotional_keywords": [],
        "positive_keywords": [],
        "negative_keywords": [],
        "industry_positive_keywords": [],
        "industry_negative_keywords": [],
        "event_positive_keywords": [],
        "event_negative_keywords": [],
        "low_credibility_hints": [],
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
        "default_stop_loss_pct": 0.05,
        "default_take_profit_pct": 0.10,
    })


def get_technical_indicators_config() -> dict:
    return get_value("technical_indicators", {
        "atr_period": 14,
        "vwap_period": 5,
        "rsi_period": 14,
        "momentum_period": 10,
        "volume_ratio_period": 5,
        "support_resistance_lookback": 20,
        "support_resistance_tolerance": 0.01,
        "stop_loss_multiplier": 2.0,
    })


def get_cache_config() -> dict:
    return get_value("cache", {
        "intent_ttl_seconds": 300,
        "intent_duplicate_window_seconds": 120,
        "intent_duplicate_threshold": 3,
        "route_log_max_entries": 1000,
    })


def get_intent_config() -> dict:
    return get_value("intent", {
        "request_limit_max": 50,
        "time_range_max_days": 180,
        "high_intent_min_screening_count": 10,
        "high_intent_min_recommend_count": 3,
        "priority": {"stock-screen": 3, "query": 2, "news-search": 1},
        "keywords": {},
        "stage_keywords": {},
    })


def get_team_config() -> dict:
    return get_value("team", {
        "trigger_keywords": [],
        "preconfigured_expert_agents": {},
        "expected_expert_agents": {},
    })


def get_akshare_config() -> dict:
    return get_value("akshare", {
        "enabled": True,
        "default_history_days": 60,
        "default_adjust": "qfq",
        "fund_flow_days": 120,
        "news_limit": 10,
    })


def get_market_holidays() -> list:
    return get_value("market.a_share_holidays_2026", [])


def get_version() -> str:
    return get_value("version", "2.6.0")


if __name__ == "__main__":
    print("=== 配置加载测试 ===")
    print(f"配置文件路径: {get_config_path()}")
    print(f"配置文件存在: {get_config_path().exists()}")
    print(f"版本: {get_version()}")
    print()
    print("=== 评分权重 ===")
    print(get_scoring_weights())
    print()
    print("=== 意图配置 ===")
    intent = get_intent_config()
    print(f"请求上限: {intent.get('request_limit_max')}")
    print(f"时间范围上限: {intent.get('time_range_max_days')} 天")
    print()
    print("=== 团队配置 ===")
    team = get_team_config()
    print(f"触发关键词: {len(team.get('trigger_keywords', []))} 个")
    print(f"预配置专家: {len(team.get('preconfigured_expert_agents', {}))} 个")
    print()
    print("=== AKShare 配置 ===")
    akshare = get_akshare_config()
    print(f"启用: {akshare.get('enabled')}")
    print(f"默认历史天数: {akshare.get('default_history_days')}")
