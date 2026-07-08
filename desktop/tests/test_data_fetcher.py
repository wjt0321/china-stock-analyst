from unittest.mock import MagicMock
from desktop.data_fetcher import DataFetcher


def test_fetch_aggregates_sources():
    config = MagicMock()
    config.get_source_priority.return_value = ["eastmoney", "sina"]
    storage = MagicMock()
    fetcher = DataFetcher(config, storage)

    em = MagicMock()
    em.name = "eastmoney"
    em.fetch_quote.return_value = MagicMock(price=10.0, change=0.5)
    sina = MagicMock()
    sina.name = "sina"
    sina.fetch_quote.return_value = MagicMock(price=10.1, change=0.4)

    result = fetcher.fetch("600519", scrapers=[em, sina])
    assert "eastmoney" in result
    assert result["eastmoney"]["price"] == 10.0
