import json
import sys
from io import StringIO
from unittest.mock import MagicMock, patch
from desktop.service import Service


def _make_service():
    storage = MagicMock()
    storage.init_schema = MagicMock()
    config = MagicMock()
    config.get.return_value = "mock_value"
    config.get_source_priority.return_value = ["eastmoney", "sina"]
    config.get_llm_config.return_value = {"enabled": False}
    config.get_analysis_config.return_value = {"short_term_weight": 0.4}
    fetcher = MagicMock()
    fetcher.fetch.return_value = {"akshare": {"price": 10.0}}
    validator = MagicMock()
    validator.validate.return_value = {"price": {"value": 10.0}}
    engine = MagicMock()
    engine.analyze.return_value = {"stock_code": "600519", "verdict": "观察"}
    renderer = MagicMock()
    renderer.render.return_value = "# Report"
    llm = MagicMock()
    llm.enhance.return_value = None
    return Service(storage, config, fetcher, validator, engine, renderer, llm)


def test_service_handle_analyze():
    service = _make_service()
    cmd = {"cmd": "analyze", "codes": ["600519"], "mode": "single", "request_id": "r1"}
    result = service.handle(cmd)
    assert result["status"] == "success"
    assert result["request_id"] == "r1"
    assert result["mode"] == "single"
    assert len(result["data"]) == 1
    assert result["data"][0]["stock_code"] == "600519"


def test_service_handle_watchlist():
    service = _make_service()
    service.storage.get_watchlist.return_value = [{"stock_code": "600519", "stock_name": "贵州茅台"}]
    cmd = {"cmd": "watchlist", "request_id": "r2"}
    result = service.handle(cmd)
    assert result["status"] == "success"
    assert result["request_id"] == "r2"
    assert result["data"][0]["stock_code"] == "600519"


def test_service_handle_settings_get_all():
    service = _make_service()
    cmd = {"cmd": "settings", "action": "get", "request_id": "r3"}
    result = service.handle(cmd)
    assert result["status"] == "success"
    assert result["request_id"] == "r3"
    assert "source_priority" in result["data"]
    assert "llm_config" in result["data"]
    assert "analysis_config" in result["data"]


def test_service_handle_settings_get_key():
    service = _make_service()
    cmd = {"cmd": "settings", "action": "get", "key": "source_priority", "request_id": "r4"}
    result = service.handle(cmd)
    assert result["status"] == "success"
    assert result["request_id"] == "r4"
    assert result["data"] == "mock_value"
    service.config.get.assert_called_once_with("source_priority")


def test_service_handle_settings_set():
    service = _make_service()
    cmd = {"cmd": "settings", "action": "set", "key": "source_priority", "value": ["akshare"], "request_id": "r5"}
    result = service.handle(cmd)
    assert result["status"] == "success"
    assert result["request_id"] == "r5"
    service.config.set.assert_called_once_with("source_priority", ["akshare"])


def test_service_handle_reports():
    service = _make_service()
    service.storage.get_reports.return_value = [{"stock_code": "600519", "mode": "single"}]
    cmd = {"cmd": "reports", "request_id": "r6"}
    result = service.handle(cmd)
    assert result["status"] == "success"
    assert result["request_id"] == "r6"
    assert result["data"][0]["stock_code"] == "600519"


def test_service_handle_unknown_command():
    service = _make_service()
    cmd = {"cmd": "unknown", "request_id": "r7"}
    result = service.handle(cmd)
    assert result["status"] == "error"
    assert result["error_code"] == "UNKNOWN_COMMAND"
    assert result["request_id"] == "r7"


def test_service_handle_analyze_missing_codes():
    service = _make_service()
    cmd = {"cmd": "analyze", "codes": [], "mode": "single", "request_id": "r8"}
    result = service.handle(cmd)
    assert result["status"] == "error"
    assert result["error_code"] == "MISSING_CODES"
    assert result["request_id"] == "r8"


def test_service_handle_analyze_source_all_failed():
    service = _make_service()
    service.fetcher.fetch.return_value = {}
    cmd = {"cmd": "analyze", "codes": ["600519"], "mode": "single", "request_id": "r9"}
    result = service.handle(cmd)
    assert result["status"] == "error"
    assert result["error_code"] == "SOURCE_ALL_FAILED"
    assert result["request_id"] == "r9"


def test_service_handle_analyze_with_llm_enhancement():
    service = _make_service()
    service.llm.enhance.return_value = "AI解读内容"
    cmd = {"cmd": "analyze", "codes": ["600519"], "mode": "single", "request_id": "r10"}
    result = service.handle(cmd)
    assert result["status"] == "success"
    report = result["data"][0]
    assert "ai_enhancement" in report["report_json"]
    assert "AI 增强解读" in report["report_md"]


def test_main_rejects_invalid_json():
    service = _make_service()
    stdin = StringIO('not json\n')
    stdout = StringIO()
    with patch("desktop.service.Service", return_value=service):
        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            try:
                from desktop.service import main
                main()
            except SystemExit:
                pass
    out = stdout.getvalue()
    assert '"status": "error"' in out
    assert '"error_code": "INVALID_JSON"' in out
