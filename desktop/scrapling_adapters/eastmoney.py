import logging
import requests

from desktop.scrapling_adapters.base import BaseStockScraper, QuoteSnapshot, NewsItem, FundFlow

LOGGER = logging.getLogger(__name__)

# Eastmoney uses numeric exchange prefixes:
# 0=SZ, 1=SH, 116=HK, etc.
_EXCHANGE_PREFIX = {
    "6": "1",  # Shanghai
    "0": "0",  # Shenzhen
    "3": "0",  # Shenzhen ChiNext
    "8": "0",  # Beijing (simplified)
    "4": "0",  # Beijing
    "9": "1",  # B-shares SH
    "2": "0",  # B-shares SZ
}


class EastmoneyScraper(BaseStockScraper):
    name = "eastmoney"
    priority = 3
    enabled = True

    def _secid(self, stock_code: str) -> str:
        prefix = _EXCHANGE_PREFIX.get(stock_code[0], "0")
        return f"{prefix}.{stock_code}"

    def fetch_quote(self, stock_code: str) -> QuoteSnapshot:
        secid = self._secid(stock_code)
        url = (
            "https://push2.eastmoney.com/api/qt/stock/get"
            f"?secid={secid}&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60"
        )
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            data = resp.json().get("data", {})
            if not data:
                return QuoteSnapshot()

            # Prices are returned multiplied by 100 for precision.
            price = data.get("f43")
            high = data.get("f44")
            low = data.get("f45")
            open_ = data.get("f46")
            prev_close = data.get("f60")

            def div100(v):
                return float(v) / 100 if v is not None else None

            current = div100(price)
            change = None
            if current is not None and prev_close is not None:
                change = current - div100(prev_close)

            return QuoteSnapshot(
                price=current,
                change=change,
                open=div100(open_),
                high=div100(high),
                low=div100(low),
                turnover=_to_float(data.get("f48")),
                volume=_to_float(data.get("f47")),
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
