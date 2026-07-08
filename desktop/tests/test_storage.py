import pytest
from pathlib import Path
from desktop.storage import Storage


def test_storage_init_and_watchlist(tmp_path):
    db = Storage(tmp_path / "test.db")
    db.init_schema()
    db.save_watchlist_item("600519", "贵州茅台", sort_order=1)
    items = db.get_watchlist()
    assert len(items) == 1
    assert items[0]["stock_code"] == "600519"
    assert items[0]["stock_name"] == "贵州茅台"


def test_watchlist_sort_order_and_update(tmp_path):
    db = Storage(tmp_path / "test.db")
    db.init_schema()
    db.save_watchlist_item("000001", "平安银行", sort_order=2)
    db.save_watchlist_item("600519", "贵州茅台", sort_order=1)
    db.save_watchlist_item("000001", "Pingan Bank", sort_order=0)
    items = db.get_watchlist()
    assert len(items) == 2
    assert [item["stock_code"] for item in items] == ["000001", "600519"]
    assert items[0]["stock_name"] == "Pingan Bank"


def test_save_and_get_raw_data(tmp_path):
    db = Storage(tmp_path / "test.db")
    db.init_schema()
    db.save_raw_data(
        "600519",
        "eastmoney",
        "close_price",
        1788.0,
        fetched_at="2025-07-08T10:00:00",
    )
    rows = db.get_raw_data("600519", "close_price", "2025-07-08")
    assert len(rows) == 1
    assert rows[0]["source"] == "eastmoney"
    assert rows[0]["value"] == "1788.0"


def test_save_and_get_report(tmp_path):
    db = Storage(tmp_path / "test.db")
    db.init_schema()
    report_id = db.save_report(
        "600519",
        "fundamental",
        "# Report",
        {"score": 85, "signals": ["buy"]},
    )
    assert isinstance(report_id, int)
    reports = db.get_reports("600519")
    assert len(reports) == 1
    assert reports[0]["mode"] == "fundamental"


def test_get_reports_filter_by_stock_code(tmp_path):
    db = Storage(tmp_path / "test.db")
    db.init_schema()
    db.save_report("600519", "technical", "md", {})
    db.save_report("000001", "technical", "md", {})
    reports = db.get_reports("600519")
    assert len(reports) == 1
    assert reports[0]["stock_code"] == "600519"
    all_reports = db.get_reports()
    assert len(all_reports) == 2


def test_save_and_get_setting(tmp_path):
    db = Storage(tmp_path / "test.db")
    db.init_schema()
    db.save_setting("api_key", "secret123")
    assert db.get_setting("api_key") == "secret123"
    db.save_setting("api_key", "secret456")
    assert db.get_setting("api_key") == "secret456"
    assert db.get_setting("missing", "default") == "default"
    assert db.get_setting("missing") is None


def test_delete_watchlist_item(tmp_path):
    db = Storage(tmp_path / "test.db")
    db.init_schema()
    db.save_watchlist_item("600519", "贵州茅台")
    db.save_watchlist_item("000001", "平安银行")
    db.delete_watchlist_item("600519")
    items = db.get_watchlist()
    assert len(items) == 1
    assert items[0]["stock_code"] == "000001"


def test_delete_report(tmp_path):
    db = Storage(tmp_path / "test.db")
    db.init_schema()
    db.save_report("600519", "single", "# Report", {})
    report_id = db.save_report("000001", "single", "# Report 2", {})
    db.delete_report(report_id)
    reports = db.get_reports()
    assert len(reports) == 1
    assert reports[0]["stock_code"] == "600519"

def test_log_source(tmp_path):
    db = Storage(tmp_path / "test.db")
    db.init_schema()
    db.log_source("eastmoney", "ok", stock_code="600519", message="fetched")
    db.log_source("sina", "error", message="timeout")
    with db._connect() as conn:
        rows = conn.execute("SELECT * FROM source_logs ORDER BY id").fetchall()
    assert len(rows) == 2
    assert rows[0]["stock_code"] == "600519"
    assert rows[1]["message"] == "timeout"


def test_db_path_parent_created(tmp_path):
    nested = tmp_path / "a" / "b" / "test.db"
    db = Storage(nested)
    db.init_schema()
    assert nested.exists()
