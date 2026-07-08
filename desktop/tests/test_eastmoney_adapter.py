from unittest.mock import MagicMock, patch
from desktop.scrapling_adapters.eastmoney import EastmoneyScraper


def test_fetch_quote_parses_price():
    scraper = EastmoneyScraper()
    mock_page = MagicMock()
    mock_page.css_first.return_value.text = "10.50"
    with patch("scrapling.fetchers.StealthyFetcher.fetch", return_value=mock_page):
        quote = scraper.fetch_quote("600519")
    assert quote.price == 10.5
