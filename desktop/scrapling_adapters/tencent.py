import logging

import requests

from desktop.scrapling_adapters.base import BaseStockScraper, QuoteSnapshot

LOGGER = logging.getLogger(__name__)

# Tencent real-time quote plain text API field order (split by ~):
# 0 symbol, 1 name, 2 code, 3 current price, 4 prev close, 5 open,
# 6 volume, 7 bid volume, 8 ask volume, ... 33 high, 34 low, ...
_TENCENT_FIELDS = {
    "price": 3,
    "prev_close": 4,
    "open": 5,
    "volume": 6,
    "high": 33,
    "low": 34,
}


class TencentScraper(BaseStockScraper):
    name = "tencent"
    priority = 4
    enabled = True

    def _symbol(self, stock_code: str) -> str:
        return f"sh{stock_code}" if stock_code.startswith("6") else f"sz{stock_code}"

    def fetch_quote(self, stock_code: str) -> QuoteSnapshot:
        symbol = self._symbol(stock_code)
        url = f"https://qt.gtimg.cn/q={symbol}"
        try:
            resp = requests.get(
                url,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://stockapp.finance.qq.com",
                },
            )
            resp.raise_for_status()
            text = resp.text
            prefix = f'v_{symbol}="'
            if prefix not in text:
                return QuoteSnapshot()
            data_str = text.split(prefix, 1)[1].split('"', 1)[0]
            if not data_str:
                return QuoteSnapshot()
            parts = data_str.split("~")

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
            )
        except Exception as e:
            LOGGER.error(f"Tencent fetch_quote failed: {e}")
            return QuoteSnapshot()


def _float(parts: list[str], field: str) -> float | None:
    idx = _TENCENT_FIELDS.get(field)
    if idx is None or idx >= len(parts):
        return None
    try:
        return float(parts[idx])
    except ValueError:
        return None
