import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from desktop.scrapling_adapters.base import BaseStockScraper
from desktop.config_manager import ConfigManager
from desktop.storage import Storage
from scripts.akshare_adapter import AKShareAdapter

LOGGER = logging.getLogger(__name__)


class DataFetcher:
    def __init__(self, config: ConfigManager, storage: Storage):
        self.config = config
        self.storage = storage
        self.akshare = AKShareAdapter()

    def fetch(
        self,
        stock_code: str,
        scrapers: Optional[list[BaseStockScraper]] = None,
    ) -> dict:
        result: dict = {}

        # AKShare
        try:
            if self.akshare.available:
                full = self.akshare.get_full_data(stock_code)
                result["akshare"] = {
                    "price": full.bid_ask.get("最新价") if full.bid_ask else None,
                    "candles": full.candles,
                    "fund_flow": full.fund_flow,
                    "news": full.news,
                }
                self.storage.log_source("akshare", "success", stock_code)
        except Exception as e:
            LOGGER.error(f"AKShare fetch failed: {e}")
            self.storage.log_source("akshare", "failed", stock_code, str(e))

        # Scrapling sources
        scrapers = scrapers or []
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_scraper = {
                executor.submit(scraper.fetch_quote, stock_code): scraper
                for scraper in scrapers
                if scraper.enabled
            }
            for future in as_completed(future_to_scraper, timeout=30):
                scraper = future_to_scraper[future]
                try:
                    quote = future.result()
                    result[scraper.name] = {
                        "price": quote.price,
                        "change": quote.change,
                        "turnover": quote.turnover,
                    }
                    self.storage.log_source(scraper.name, "success", stock_code)
                except Exception as e:
                    LOGGER.error(f"{scraper.name} fetch failed: {e}")
                    self.storage.log_source(scraper.name, "failed", stock_code, str(e))

        return result
