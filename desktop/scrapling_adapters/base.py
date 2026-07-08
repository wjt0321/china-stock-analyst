from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class QuoteSnapshot:
    price: Optional[float] = None
    change: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None
    turnover: Optional[float] = None
    name: Optional[str] = None
    timestamp: Optional[str] = None


@dataclass
class NewsItem:
    title: str = ""
    snippet: str = ""
    url: str = ""
    publish_time: Optional[str] = None
    source: str = ""


@dataclass
class FundFlow:
    main_net: Optional[float] = None
    retail_net: Optional[float] = None
    date: Optional[str] = None


class BaseStockScraper(ABC):
    name: str = ""
    priority: int = 99
    enabled: bool = True

    @abstractmethod
    def fetch_quote(self, stock_code: str) -> QuoteSnapshot:
        raise NotImplementedError

    def fetch_news(self, stock_code: str, limit: int = 10) -> list[NewsItem]:
        return []

    def fetch_fund_flow(self, stock_code: str) -> list[FundFlow]:
        return []

    def health_check(self, stock_code: str = "600519") -> bool:
        try:
            quote = self.fetch_quote(stock_code)
            return quote.price is not None
        except Exception:
            return False
