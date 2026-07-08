from desktop.quant_flow import calc_proxy_fund_flow


def test_proxy_fund_flow_detects_inflow():
    # 5 days of rising closes above midpoint -> buy pressure
    candles = [
        {"date": "2026-07-0%d" % i, "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.4, "volume": 10000}
        for i in range(1, 6)
    ]
    result = calc_proxy_fund_flow(candles)
    assert result["direction"] == "inflow"
    assert result["recent_net_pct"] > 0
    assert "流入" in result["summary"]


def test_proxy_fund_flow_detects_outflow():
    # 5 days of falling closes below midpoint -> sell pressure
    candles = [
        {"date": "2026-07-0%d" % i, "open": 10.5, "high": 10.6, "low": 9.8, "close": 9.9, "volume": 10000}
        for i in range(1, 6)
    ]
    result = calc_proxy_fund_flow(candles)
    assert result["direction"] == "outflow"
    assert result["recent_net_pct"] < 0
    assert "流出" in result["summary"]


def test_proxy_fund_flow_empty_candles():
    result = calc_proxy_fund_flow([])
    assert result["direction"] == "neutral"
    assert result["summary"] == "无有效K线数据，无法估算资金流向"


def test_proxy_fund_flow_counts_days():
    candles = [
        {"date": "2026-07-01", "open": 10.0, "high": 10.5, "low": 9.5, "close": 10.3, "volume": 1000},
        {"date": "2026-07-02", "open": 10.3, "high": 10.4, "low": 9.6, "close": 9.7, "volume": 1000},
    ]
    result = calc_proxy_fund_flow(candles)
    assert result["inflow_days"] == 1
    assert result["outflow_days"] == 1
