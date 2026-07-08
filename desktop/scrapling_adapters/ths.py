import json
import logging
import re

import requests

from desktop.scrapling_adapters.base import BaseStockScraper, QuoteSnapshot

LOGGER = logging.getLogger(__name__)


class ThsScraper(BaseStockScraper):
    name = "ths"
    priority = 3
    # Disabled by default: its JSONP endpoint is unreliable outside trading hours
    # and frequently returns empty/placeholder data.
    enabled = False

    def _symbol(self, stock_code: str) -> str:
        return f"hs_{stock_code}"

    def fetch_quote(self, stock_code: str) -> QuoteSnapshot:
        symbol = self._symbol(stock_code)
        url = f"http://d.10jqka.com.cn/v6/time/{symbol}/today"
        try:
            resp = requests.get(
                url,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "http://stockpage.10jqka.com.cn/",
                },
            )
            resp.raise_for_status()
            text = resp.text
            # Strip JSONP wrapper: quotebridge_v6_time_hs_600519_today(...)
            match = re.search(r"\((\{.*\})\)", text)
            if not match:
                return QuoteSnapshot()
            data = json.loads(match.group(1)).get(symbol, {})
            if not data:
                return QuoteSnapshot()

            price = _to_float(data.get("latest"))
            prev = _to_float(data.get("pre"))
            change = None
            if price is not None and prev is not None and prev != 0:
                change = price - prev

            return QuoteSnapshot(
                price=price,
                change=change,
                open=_to_float(data.get("open")),
                high=_to_float(data.get("high")),
                low=_to_float(data.get("low")),
                volume=_to_float(data.get("totalVolume")),
                turnover=_to_float(data.get("totalAmount")),
            )
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
