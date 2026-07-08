import json
import logging
import sys
from pathlib import Path

from desktop.config_manager import ConfigManager
from desktop.storage import Storage
from desktop.data_fetcher import DataFetcher
from desktop.data_validator import DataValidator
from desktop.analysis_engine import AnalysisEngine
from desktop.report_renderer import ReportRenderer
from desktop.llm_adapter import LLMAdapter
from desktop.scrapling_adapters.eastmoney import EastmoneyScraper
from desktop.scrapling_adapters.sina import SinaScraper
from desktop.scrapling_adapters.ths import ThsScraper
from desktop.scrapling_adapters.tencent import TencentScraper

LOGGER = logging.getLogger(__name__)


class Service:
    def __init__(
        self,
        storage: Storage,
        config: ConfigManager,
        fetcher: DataFetcher,
        validator: DataValidator,
        engine: AnalysisEngine,
        renderer: ReportRenderer,
        llm: LLMAdapter,
    ):
        self.storage = storage
        self.config = config
        self.fetcher = fetcher
        self.validator = validator
        self.engine = engine
        self.renderer = renderer
        self.llm = llm
        self.scrapers = [EastmoneyScraper(), SinaScraper(), ThsScraper(), TencentScraper()]

    def handle(self, cmd: dict) -> dict:
        command = cmd.get("cmd")
        request_id = cmd.get("request_id", "")
        try:
            if command == "analyze":
                return {**self._handle_analyze(cmd), "request_id": request_id}
            if command == "watchlist":
                return {"status": "success", "data": self.storage.get_watchlist(), "request_id": request_id}
            if command == "settings":
                return self._handle_settings(cmd, request_id)
            if command == "reports":
                return {"status": "success", "data": self.storage.get_reports(), "request_id": request_id}
            return {"status": "error", "error_code": "UNKNOWN_COMMAND", "message": f"Unknown command: {command}", "request_id": request_id}
        except Exception as e:
            LOGGER.exception("Command failed")
            return {"status": "error", "error_code": "INTERNAL_ERROR", "message": str(e), "request_id": request_id}

    def _handle_analyze(self, cmd: dict) -> dict:
        codes = cmd.get("codes", [])
        mode = cmd.get("mode", "single")
        if not codes:
            return {"status": "error", "error_code": "MISSING_CODES", "message": "No stock codes provided"}

        results = []
        for code in codes:
            raw = self.fetcher.fetch(code, scrapers=self.scrapers)
            if not raw:
                return {"status": "error", "error_code": "SOURCE_ALL_FAILED", "message": f"All sources failed for {code}"}

            validated = self.validator.validate(code, raw)
            report_json = self.engine.analyze(code, validated)
            report_md = self.renderer.render(report_json)
            enhanced = self.llm.enhance(report_json)
            if enhanced:
                report_json["ai_enhancement"] = enhanced
                report_md += f"\n\n## AI 增强解读\n\n{enhanced}"

            self.storage.save_report(code, mode, report_md, report_json)
            results.append({"stock_code": code, "report_md": report_md, "report_json": report_json})

        return {"status": "success", "mode": mode, "data": results}

    def _handle_settings(self, cmd: dict, request_id: str) -> dict:
        action = cmd.get("action", "get")
        if action == "get":
            key = cmd.get("key")
            value = self.config.get(key) if key else {
                "source_priority": self.config.get_source_priority(),
                "llm_config": self.config.get_llm_config(),
                "analysis_config": self.config.get_analysis_config(),
            }
            return {"status": "success", "data": value, "request_id": request_id}
        if action == "set":
            key = cmd.get("key")
            value = cmd.get("value")
            if key is None:
                return {"status": "error", "error_code": "MISSING_KEY", "message": "Missing required 'key' for settings set", "request_id": request_id}
            if value is None:
                return {"status": "error", "error_code": "MISSING_KEY", "message": "Missing required 'value' for settings set", "request_id": request_id}
            self.config.set(key, value)
            return {"status": "success", "request_id": request_id}
        return {"status": "error", "error_code": "INVALID_SETTINGS_ACTION", "message": f"Invalid settings action: {action}", "request_id": request_id}


def main():
    logging.basicConfig(level=logging.INFO, filename="desktop.log", filemode="a")
    base_dir = Path(__file__).resolve().parent.parent
    db_path = base_dir / "data" / "app.db"
    storage = Storage(db_path)
    storage.init_schema()
    config = ConfigManager(storage, defaults_path=base_dir / "config" / "settings.json")
    fetcher = DataFetcher(config, storage)
    validator = DataValidator(config)
    engine = AnalysisEngine(config)
    renderer = ReportRenderer()
    llm = LLMAdapter(config)

    service = Service(storage, config, fetcher, validator, engine, renderer, llm)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            cmd = json.loads(line)
        except json.JSONDecodeError as e:
            print(json.dumps({"status": "error", "error_code": "INVALID_JSON", "message": str(e)}))
            continue
        result = service.handle(cmd)
        print(json.dumps(result, ensure_ascii=False))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
