import pytest
from dataclasses import dataclass
from desktop.scrapling_adapters.base import BaseStockScraper, QuoteSnapshot


class DummyScraper(BaseStockScraper):
    name = "dummy"
    priority = 1
    enabled = True

    def fetch_quote(self, stock_code: str) -> QuoteSnapshot:
        return QuoteSnapshot(price=10.0, change=0.5, turnover=1000.0)


def test_dummy_scraper():
    s = DummyScraper()
    q = s.fetch_quote("600519")
    assert q.price == 10.0
