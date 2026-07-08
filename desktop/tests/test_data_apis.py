from unittest.mock import MagicMock, patch

from desktop.data_apis import SinaKlineAPI, TencentKlineAPI


def test_tencent_fetch_candles_parses_qfqday():
    api = TencentKlineAPI()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "code": 0,
        "msg": "",
        "data": {
            "sh600519": {
                "qfqday": [
                    ["2026-07-01", "1180.1", "1193.01", "1196.8", "1166.33", "42474.0"],
                    ["2026-07-02", "1193.01", "1203.0", "1215.52", "1190.51", "50870.0"],
                ]
            }
        },
    }
    with patch("desktop.data_apis.requests.get", return_value=mock_resp):
        candles = api.fetch_candles("600519", days=2)
    assert len(candles) == 2
    assert candles[0]["date"] == "2026-07-01"
    assert candles[0]["open"] == 1180.1
    assert candles[0]["close"] == 1193.01
    assert candles[0]["high"] == 1196.8
    assert candles[0]["low"] == 1166.33
    assert candles[0]["volume"] == 42474.0


def test_sina_fetch_candles_parses_json_list():
    api = SinaKlineAPI()
    mock_resp = MagicMock()
    mock_resp.json.return_value = [
        {
            "day": "2026-07-01",
            "open": "1180.10",
            "high": "1196.80",
            "low": "1166.33",
            "close": "1193.01",
            "volume": "4247400",
            "ma_price5": 1190.0,
        },
        {
            "day": "2026-07-02",
            "open": "1193.01",
            "high": "1215.52",
            "low": "1190.51",
            "close": "1203.00",
            "volume": "5087000",
            "ma_price5": 1192.0,
        },
    ]
    with patch("desktop.data_apis.requests.get", return_value=mock_resp):
        candles = api.fetch_candles("600519", days=2)
    assert len(candles) == 2
    assert candles[1]["date"] == "2026-07-02"
    assert candles[1]["close"] == 1203.0
    assert candles[1]["volume"] == 5087000.0


def test_tencent_fetch_candles_returns_empty_on_error():
    api = TencentKlineAPI()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"code": 0, "data": {}}
    with patch("desktop.data_apis.requests.get", return_value=mock_resp):
        candles = api.fetch_candles("600519")
    assert candles == []


def test_sina_fetch_candles_returns_empty_on_error():
    api = SinaKlineAPI()
    mock_resp = MagicMock()
    mock_resp.json.return_value = None
    with patch("desktop.data_apis.requests.get", return_value=mock_resp):
        candles = api.fetch_candles("600519")
    assert candles == []
