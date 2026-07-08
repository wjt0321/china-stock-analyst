import logging
from desktop.scrapling_adapters.base import BaseStockScraper, QuoteSnapshot

try:
    from scrapling.fetchers import StealthyFetcher
    _SCRAPLING_AVAILABLE = True
except ImportError:
    _SCRAPLING_AVAILABLE = False

LOGGER = logging.getLogger(__name__)


class TencentScraper(BaseStockScraper):
    name = "tencent"
    priority = 4
    enabled = True

    def __init__(self):
        self.fetcher = StealthyFetcher() if _SCRAPLING_AVAILABLE else None

    def fetch_quote(self, stock_code: str) -> QuoteSnapshot:
        if not self.fetcher:
            return QuoteSnapshot()
        symbol = f"sh{stock_code}" if stock_code.startswith("6") else f"sz{stock_code}"
        url = f"https://qt.gtimg.cn/q={symbol}"
        try:
            # Timeouts are enforced by DataFetcher at the orchestration level.
            page = self.fetcher.fetch(url, headless=True, network_idle=True)
            # Tencent quote API returns plain text; parse accordingly
            text = page.text or ""
            parts = text.split("~")
            if len(parts) > 3:
                return QuoteSnapshot(price=_to_float(parts[3]))
            return QuoteSnapshot()
        except Exception as e:
            LOGGER.error(f"Tencent fetch_quote failed: {e}")
            return QuoteSnapshot()


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None
