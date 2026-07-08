import logging

import requests

from desktop.scrapling_adapters.base import BaseStockScraper, QuoteSnapshot

LOGGER = logging.getLogger(__name__)

# Tencent real-time quote plain text API field order (split by ~).
# Verified stable fields across A-shares: price, prev_close, open, volume,
# high, low, turnover, turnover_rate, pe_ttm, change_pct.  Indices beyond 39
# are not consistent across all stocks, so we compute amplitude ourselves.
_TENCENT_FIELDS = {
    "price": 3,
    "prev_close": 4,
    "open": 5,
    "volume": 6,
    "high": 33,
    "low": 34,
    "turnover": 37,  # 万元
    "turnover_rate": 38,  # %
    "pe_ttm": 39,
    "change_pct": 32,  # %
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
            change = _float(parts, "change_pct")
            if change is None and price is not None and prev is not None:
                change = price - prev

            high = _float(parts, "high")
            low = _float(parts, "low")
            amplitude = None
            if high is not None and low is not None and prev and prev != 0:
                amplitude = (high - low) / prev * 100

            name = parts[1] if len(parts) > 1 else None

            return QuoteSnapshot(
                price=price,
                change=change,
                open=_float(parts, "open"),
                high=high,
                low=low,
                volume=_float(parts, "volume"),
                turnover=_float(parts, "turnover"),
                name=name,
                pe_ttm=_float(parts, "pe_ttm"),
                turnover_rate=_float(parts, "turnover_rate"),
                amplitude=amplitude,
                change_pct=_float(parts, "change_pct"),
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
