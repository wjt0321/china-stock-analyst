from unittest.mock import MagicMock, patch

from desktop.scrapling_adapters.eastmoney import EastmoneyScraper


def test_fetch_quote_parses_price():
    scraper = EastmoneyScraper()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "rc": 0,
        "data": {
            "f43": 1050,
            "f44": 1100,
            "f45": 1000,
            "f46": 1020,
            "f47": 10000,
            "f48": 500000,
            "f60": 1000,
        },
    }
    with patch("desktop.scrapling_adapters.eastmoney.requests.get", return_value=mock_resp):
        quote = scraper.fetch_quote("600519")
    assert quote.price == 10.5
    assert quote.change == 0.5
    assert quote.high == 11.0
    assert quote.low == 10.0
