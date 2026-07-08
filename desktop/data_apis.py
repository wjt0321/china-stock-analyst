import logging
from abc import ABC, abstractmethod
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)

# Standard OHLCV field names returned by every data API.
# Keepers of this module should preserve this contract so that downstream
# `scripts.technical_indicators` can consume candles without source-specific code.
CANDLE_FIELDS = ["date", "open", "high", "low", "close", "volume"]


class DataAPI(ABC):
    """Abstract base for lightweight HTTP data sources.

    Implementations must be stateless and safe to call from a thread pool.
    """

    name: str = ""
    enabled: bool = True

    @abstractmethod
    def fetch_candles(self, stock_code: str, days: int = 60) -> list[dict[str, Any]]:
        """Return a list of daily OHLCV dictionaries, oldest first."""
        raise NotImplementedError


class TencentKlineAPI(DataAPI):
    """Tencent K-line HTTP API (no authentication required).

    Endpoint returns adjusted daily candles in the format:
        [date, open, close, high, low, volume]
    """

    name = "tencent"
    enabled = True

    def _symbol(self, stock_code: str) -> str:
        return f"sh{stock_code}" if stock_code.startswith("6") else f"sz{stock_code}"

    def fetch_candles(self, stock_code: str, days: int = 60) -> list[dict[str, Any]]:
        symbol = self._symbol(stock_code)
        url = (
            "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            f"?param={symbol},day,,,{days},qfq"
        )
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
            payload = resp.json()
            records = (
                payload.get("data", {})
                .get(symbol, {})
                .get("qfqday", [])
            )
            candles = []
            for row in records:
                if len(row) < 6:
                    continue
                candles.append(
                    {
                        "date": str(row[0]),
                        "open": float(row[1]),
                        "close": float(row[2]),
                        "high": float(row[3]),
                        "low": float(row[4]),
                        "volume": float(row[5]),
                    }
                )
            return candles
        except Exception as e:
            LOGGER.error(f"Tencent K-line fetch failed for {stock_code}: {e}")
            return []


class SinaKlineAPI(DataAPI):
    """Sina K-line HTTP API (no authentication required).

    Endpoint returns daily/weekly/etc. candles as JSON objects with keys:
        day, open, high, low, close, volume, ma_price5, ma_volume5, ...
    We request `scale=240` (240 minutes = daily bar) to mimic daily candles.
    """

    name = "sina"
    enabled = True

    def _symbol(self, stock_code: str) -> str:
        return f"sh{stock_code}" if stock_code.startswith("6") else f"sz{stock_code}"

    def fetch_candles(self, stock_code: str, days: int = 60) -> list[dict[str, Any]]:
        symbol = self._symbol(stock_code)
        url = (
            "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            f"CN_MarketData.getKLineData?symbol={symbol}&scale=240&ma=5&datalen={days}"
        )
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
            records = resp.json()
            if not isinstance(records, list):
                return []
            candles = []
            for row in records:
                candles.append(
                    {
                        "date": str(row["day"]),
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": float(row["volume"]),
                    }
                )
            return candles
        except Exception as e:
            LOGGER.error(f"Sina K-line fetch failed for {stock_code}: {e}")
            return []


def get_default_data_apis() -> list[DataAPI]:
    """Return the enabled set of non-AKShare HTTP data APIs."""
    return [SinaKlineAPI(), TencentKlineAPI()]


if __name__ == "__main__":
    stock_code = "600519"
    for api in get_default_data_apis():
        candles = api.fetch_candles(stock_code, days=5)
        print(f"=== {api.name} ===")
        print(f"count: {len(candles)}")
        for c in candles[:3]:
            print(c)
