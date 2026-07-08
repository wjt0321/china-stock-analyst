from unittest.mock import MagicMock
from desktop.data_validator import DataValidator


def _make_validator():
    config = MagicMock()
    config.get_source_priority.return_value = ["eastmoney", "sina", "ths", "tencent", "akshare"]
    config.get_analysis_config.return_value = {
        "price_conflict_threshold": 0.01,
        "change_conflict_threshold": 0.012,
        "fund_flow_conflict_threshold": 0.35,
    }
    return DataValidator(config)


def test_majority_vote_price():
    validator = _make_validator()
    raw = {
        "eastmoney": {"price": 10.0},
        "sina": {"price": 10.0},
        "ths": {"price": 10.01},
        "tencent": {"price": 10.5},
    }
    result = validator.validate("600519", raw)
    assert result["price"]["value"] == 10.0
    assert result["price"]["conflict"] is True


def test_priority_fallback_when_no_majority():
    validator = _make_validator()
    raw = {
        "eastmoney": {"price": 10.0},
        "sina": {"price": 10.05},
        "ths": {"price": 10.10},
    }
    result = validator.validate("600519", raw)
    assert result["price"]["value"] == 10.0
    assert result["price"]["sources"] == ["eastmoney", "sina", "ths"]


def test_pass_through_non_numeric_data():
    validator = _make_validator()
    raw = {
        "eastmoney": {
            "price": 10.0,
            "candles": [1, 2, 3],
            "fund_flow": {"in": 100},
            "news": [{"title": "x"}],
        },
    }
    result = validator.validate("600519", raw)
    assert result["eastmoney_candles"]["value"] == [1, 2, 3]
    assert result["eastmoney_fund_flow"]["value"] == {"in": 100}
    assert result["eastmoney_news"]["value"] == [{"title": "x"}]


def test_missing_numeric_field():
    validator = _make_validator()
    raw = {"eastmoney": {"turnover": 0.05}}
    result = validator.validate("600519", raw)
    assert "price" in result
    assert result["price"]["value"] is None
    assert result["price"]["notes"] == ["无有效数据源"]
    assert result["turnover"]["value"] == 0.05


def test_median_conflict_detection():
    config = MagicMock()
    config.get_source_priority.return_value = ["eastmoney", "sina"]
    config.get_analysis_config.return_value = {
        "price_conflict_threshold": 0.01,
        "change_conflict_threshold": 0.012,
        "fund_flow_conflict_threshold": 0.35,
    }
    validator = DataValidator(config)
    raw = {
        "eastmoney": {"price": 10.0},
        "sina": {"price": 10.5},
    }
    result = validator.validate("600519", raw)
    assert result["price"]["value"] == 10.0
    assert result["price"]["conflict"] is True


def test_no_conflict_for_close_values():
    validator = _make_validator()
    raw = {
        "eastmoney": {"price": 10.0},
        "sina": {"price": 10.001},
        "ths": {"price": 10.0},
    }
    result = validator.validate("600519", raw)
    assert result["price"]["value"] == 10.0
    assert result["price"]["conflict"] is False
