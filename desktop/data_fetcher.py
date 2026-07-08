import logging
import time
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Optional

from desktop.scrapling_adapters.base import BaseStockScraper
from desktop.config_manager import ConfigManager
from desktop.storage import Storage
from scripts.akshare_adapter import AKShareAdapter

LOGGER = logging.getLogger(__name__)

# Timeouts for blocking network calls.
PER_SOURCE_TIMEOUT_SECS = 30.0
OVERALL_FETCH_TIMEOUT_SECS = 90.0


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
        overall_deadline = time.monotonic() + OVERALL_FETCH_TIMEOUT_SECS

        # AKShare
        try:
            if self.akshare.available:
                timeout = min(
                    PER_SOURCE_TIMEOUT_SECS,
                    max(0.0, overall_deadline - time.monotonic()),
                )
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self.akshare.get_full_data, stock_code)
                    done, _ = wait([future], timeout=timeout)
                    if future in done:
                        full = future.result()
                        result["akshare"] = {
                            "price": full.bid_ask.get("最新价") if full.bid_ask else None,
                            "candles": full.candles,
                            "fund_flow": full.fund_flow,
                            "news": full.news,
                        }
                        self.storage.log_source("akshare", "success", stock_code)
                    else:
                        LOGGER.warning(f"AKShare fetch timed out for {stock_code}")
                        self.storage.log_source("akshare", "timeout", stock_code)
                        future.cancel()
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
            for future, scraper in future_to_scraper.items():
                remaining = overall_deadline - time.monotonic()
                if remaining <= 0.0:
                    LOGGER.warning(
                        f"Overall fetch timeout reached; skipping {scraper.name} for {stock_code}"
                    )
                    self.storage.log_source(scraper.name, "timeout", stock_code)
                    future.cancel()
                    continue

                timeout = min(PER_SOURCE_TIMEOUT_SECS, remaining)
                try:
                    done, _ = wait([future], timeout=timeout)
                    if future not in done:
                        LOGGER.warning(
                            f"{scraper.name} fetch timed out for {stock_code}"
                        )
                        self.storage.log_source(scraper.name, "timeout", stock_code)
                        future.cancel()
                        continue

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
