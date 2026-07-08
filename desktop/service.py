from pathlib import Path
import sys

# Defensive sys.path insertion so this service can be launched from any CWD
# (e.g. the Tauri binary directory) and still import `desktop.*` and `scripts.*`.
_SERVICE_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _SERVICE_FILE.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import json
import logging
import os
import platform

from desktop.config_manager import ConfigManager
from desktop.storage import Storage
from desktop.data_apis import get_default_data_apis
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


def get_app_data_dir() -> Path:
    """Return the platform-appropriate application data directory.

    Honors the APP_DATA_DIR environment variable (set by the Tauri host)
    and falls back to:
      - Windows: %LOCALAPPDATA%/china-stock-analyst-desktop/
      - Other:   ~/.local/share/china-stock-analyst-desktop/
    """
    override = os.environ.get("APP_DATA_DIR")
    if override:
        return Path(override)

    if platform.system() == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            local_app_data = Path.home() / "AppData" / "Local"
        return Path(local_app_data) / "china-stock-analyst-desktop"

    return Path.home() / ".local" / "share" / "china-stock-analyst-desktop"


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

            stock_name = validated.get("name", {}).get("value", "")
            report_md = self.renderer.render(report_json, stock_name=stock_name)

            # Persist Markdown report to the stock-reports directory.
            try:
                base_dir = Path(__file__).resolve().parent.parent
                output_dir = Path(os.environ.get("STOCK_REPORTS_DIR", base_dir / "stock-reports"))
                report_path = self.renderer.save_to_file(report_md, code, output_dir)
                report_json["report_path"] = str(report_path)
            except Exception as e:
                LOGGER.error(f"Failed to save report file: {e}")

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
    app_data_dir = get_app_data_dir()
    app_data_dir.mkdir(parents=True, exist_ok=True)

    log_path = app_data_dir / "desktop.log"
    logging.basicConfig(level=logging.INFO, filename=str(log_path), filemode="a")

    base_dir = Path(__file__).resolve().parent.parent
    db_path = app_data_dir / "app.db"
    storage = Storage(db_path)
    storage.init_schema()
    config = ConfigManager(storage, defaults_path=base_dir / "config" / "settings.json")
    fetcher = DataFetcher(config, storage, data_apis=get_default_data_apis())
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
