import logging
import requests

from desktop.scrapling_adapters.base import BaseStockScraper, QuoteSnapshot

LOGGER = logging.getLogger(__name__)

# Sina real-time quote JS API field order for A-shares:
# 0 name, 1 open, 2 prev_close, 3 current, 4 high, 5 low, 6 buy1, 7 sell1,
# 8 volume(shares), 9 amount(CNY), 10-19 bid1-5 qty/price, 20-29 ask1-5 qty/price,
# 30 date, 31 time
_SINA_FIELDS = {
    "name": 0,
    "open": 1,
    "prev_close": 2,
    "price": 3,
    "high": 4,
    "low": 5,
    "volume": 8,
    "turnover": 9,
}


class SinaScraper(BaseStockScraper):
    name = "sina"
    priority = 2
    enabled = True

    def _symbol(self, stock_code: str) -> str:
        return f"sh{stock_code}" if stock_code.startswith("6") else f"sz{stock_code}"

    def fetch_quote(self, stock_code: str) -> QuoteSnapshot:
        symbol = self._symbol(stock_code)
        url = f"https://hq.sinajs.cn/list={symbol}"
        try:
            resp = requests.get(
                url,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://finance.sina.com.cn",
                },
            )
            resp.raise_for_status()
            text = resp.text
            prefix = f'var hq_str_{symbol}="'
            if prefix not in text:
                return QuoteSnapshot()
            data_str = text.split(prefix, 1)[1].split('"', 1)[0]
            if not data_str:
                return QuoteSnapshot()
            parts = data_str.split(",")

            price = _float(parts, "price")
            prev = _float(parts, "prev_close")
            change = None
            if price is not None and prev is not None:
                change = price - prev

            return QuoteSnapshot(
                price=price,
                change=change,
                open=_float(parts, "open"),
                high=_float(parts, "high"),
                low=_float(parts, "low"),
                volume=_float(parts, "volume"),
                turnover=_float(parts, "turnover"),
            )
        except Exception as e:
            LOGGER.error(f"Sina fetch_quote failed: {e}")
            return QuoteSnapshot()


def _float(parts: list[str], field: str) -> float | None:
    idx = _SINA_FIELDS.get(field)
    if idx is None or idx >= len(parts):
        return None
    try:
        return float(parts[idx])
    except ValueError:
        return None
