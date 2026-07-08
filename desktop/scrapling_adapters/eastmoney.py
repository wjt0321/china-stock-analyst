import logging
from desktop.scrapling_adapters.base import BaseStockScraper, QuoteSnapshot, NewsItem, FundFlow

try:
    from scrapling.fetchers import StealthyFetcher
    _SCRAPLING_AVAILABLE = True
except ImportError:
    _SCRAPLING_AVAILABLE = False

LOGGER = logging.getLogger(__name__)


class EastmoneyScraper(BaseStockScraper):
    name = "eastmoney"
    priority = 1
    enabled = True
    _quote_url = "https://quote.eastmoney.com/concept/{code}.html"

    def __init__(self):
        self.fetcher = StealthyFetcher() if _SCRAPLING_AVAILABLE else None

    def fetch_quote(self, stock_code: str) -> QuoteSnapshot:
        if not self.fetcher:
            return QuoteSnapshot()
        url = f"https://quote.eastmoney.com/{stock_code}.html"
        try:
            # Timeouts are enforced by DataFetcher at the orchestration level.
            page = self.fetcher.fetch(url, headless=True, network_idle=True)
            price_el = page.css_first(".price")
            change_el = page.css_first(".change")
            return QuoteSnapshot(
                price=_to_float(price_el.text if price_el else None),
                change=_to_float(change_el.text if change_el else None),
            )
        except Exception as e:
            LOGGER.error(f"Eastmoney fetch_quote failed: {e}")
            return QuoteSnapshot()

    def fetch_news(self, stock_code: str, limit: int = 10) -> list[NewsItem]:
        return []

    def fetch_fund_flow(self, stock_code: str) -> list[FundFlow]:
        return []


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None
