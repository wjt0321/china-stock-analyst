import json

from unittest.mock import MagicMock

from desktop.analysis_engine import AnalysisEngine


def _make_engine():
    config = MagicMock()
    config.get_analysis_config.return_value = {
        "short_term_weight": 0.40,
        "fundamental_weight": 0.35,
        "sentiment_weight": 0.25,
    }
    return AnalysisEngine(config)


def test_analysis_engine_returns_verdict():
    engine = _make_engine()
    validated = {
        "price": {"value": 10.0, "conflict": False},
        "change": {"value": 2.5, "conflict": False},
        "akshare_candles": {"value": []},
    }
    report = engine.analyze("600519", validated)
    assert "verdict" in report
    assert report["verdict"] in ["可做", "观察", "回避"]


def test_analysis_engine_with_candles_is_json_serializable():
    engine = _make_engine()
    candles = [
        {"date": "2026-04-01", "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.3, "volume": 1000000},
        {"date": "2026-04-02", "open": 10.3, "high": 10.8, "low": 10.2, "close": 10.6, "volume": 1200000},
        {"date": "2026-04-03", "open": 10.6, "high": 11.0, "low": 10.4, "close": 10.8, "volume": 1500000},
        {"date": "2026-04-07", "open": 10.8, "high": 11.2, "low": 10.7, "close": 11.0, "volume": 1800000},
        {"date": "2026-04-08", "open": 11.0, "high": 11.5, "low": 10.9, "close": 11.3, "volume": 2000000},
    ]
    validated = {
        "price": {"value": 11.3, "conflict": False},
        "change": {"value": 2.5, "conflict": False},
        "akshare_candles": {"value": candles},
    }
    report = engine.analyze("600519", validated)
    assert report["stock_code"] == "600519"
    assert report["expert_outputs"]["technical"]["evidences"]
    # Must be JSON-serializable for Tauri sidecar responses.
    json.dumps(report)
