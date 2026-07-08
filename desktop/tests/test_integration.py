from pathlib import Path
from unittest.mock import MagicMock, patch
from desktop.storage import Storage
from desktop.config_manager import ConfigManager
from desktop.data_fetcher import DataFetcher
from desktop.data_validator import DataValidator
from desktop.analysis_engine import AnalysisEngine
from desktop.report_renderer import ReportRenderer
from desktop.llm_adapter import LLMAdapter
from desktop.service import Service


def test_end_to_end_analyze(tmp_path):
    storage = Storage(tmp_path / "app.db")
    storage.init_schema()
    config = ConfigManager(storage, defaults_path=Path("nonexistent"))
    fetcher = DataFetcher(config, storage)
    validator = DataValidator(config)
    engine = AnalysisEngine(config)
    renderer = ReportRenderer()
    llm = LLMAdapter(config)
    service = Service(storage, config, fetcher, validator, engine, renderer, llm)

    # Mock all scrapers to avoid network
    service.scrapers = []

    with patch.object(fetcher.akshare, "available", True):
        with patch.object(
            fetcher.akshare,
            "get_full_data",
            return_value=MagicMock(
                stock_name="贵州茅台",
                candles=[
                    {"date": "2026-07-0%d" % i, "open": 9.0, "high": 10.0, "low": 8.5, "close": 9.5 + i * 0.1, "volume": 1000}
                    for i in range(1, 25)
                ],
                fund_flow=[{"main_net_inflow": 1000000}],
                bid_ask={"最新价": 11.0},
                news=[{"title": "测试新闻", "publish_time": "2026-07-08"}],
                success=True,
                error_message="",
            ),
        ):
            result = service.handle({"cmd": "analyze", "codes": ["600519"], "mode": "single", "request_id": "r1"})

    assert result["status"] == "success"
    assert result["data"][0]["stock_code"] == "600519"
    assert "观察" in result["data"][0]["report_md"] or "可做" in result["data"][0]["report_md"] or "回避" in result["data"][0]["report_md"]
