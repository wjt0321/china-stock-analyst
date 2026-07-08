import logging
from desktop.scrapling_adapters.base import BaseStockScraper, QuoteSnapshot

try:
    from scrapling.fetchers import StealthyFetcher
    _SCRAPLING_AVAILABLE = True
except ImportError:
    _SCRAPLING_AVAILABLE = False

LOGGER = logging.getLogger(__name__)


class ThsScraper(BaseStockScraper):
    name = "ths"
    priority = 3
    enabled = True

    def __init__(self):
        self.fetcher = StealthyFetcher() if _SCRAPLING_AVAILABLE else None

    def fetch_quote(self, stock_code: str) -> QuoteSnapshot:
        if not self.fetcher:
            return QuoteSnapshot()
        url = f"https://basic.10jqka.com.cn/{stock_code}"
        try:
            # Timeouts are enforced by DataFetcher at the orchestration level.
            page = self.fetcher.fetch(url, headless=True, network_idle=True)
            price_el = page.css_first(".price")
            return QuoteSnapshot(price=_to_float(price_el.text if price_el else None))
        except Exception as e:
            LOGGER.error(f"Ths fetch_quote failed: {e}")
            return QuoteSnapshot()


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None
