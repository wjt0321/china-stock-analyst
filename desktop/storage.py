import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class Storage:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    stock_code TEXT PRIMARY KEY,
                    stock_name TEXT NOT NULL,
                    sort_order INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS raw_data_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    source TEXT NOT NULL,
                    field TEXT NOT NULL,
                    value TEXT,
                    fetched_at TEXT NOT NULL,
                    UNIQUE(stock_code, source, field, fetched_at)
                );
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    report_md TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS source_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    stock_code TEXT,
                    status TEXT NOT NULL,
                    message TEXT,
                    created_at TEXT NOT NULL
                );
            """)

    def save_watchlist_item(self, stock_code: str, stock_name: str, sort_order: int = 0) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO watchlist (stock_code, stock_name, sort_order, created_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(stock_code) DO UPDATE SET
                   stock_name=excluded.stock_name, sort_order=excluded.sort_order""",
                (stock_code, stock_name, sort_order, datetime.now().isoformat()),
            )

    def get_watchlist(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM watchlist ORDER BY sort_order, created_at"
            ).fetchall()
            return [dict(row) for row in rows]

    def delete_watchlist_item(self, stock_code: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM watchlist WHERE stock_code = ?", (stock_code,))

    def save_raw_data(
        self,
        stock_code: str,
        source: str,
        field: str,
        value: Any,
        fetched_at: Optional[str] = None,
    ) -> None:
        fetched_at = fetched_at or datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO raw_data_cache (stock_code, source, field, value, fetched_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (stock_code, source, field, json.dumps(value, ensure_ascii=False), fetched_at),
            )

    def get_raw_data(self, stock_code: str, field: str, date: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM raw_data_cache
                   WHERE stock_code = ? AND field = ? AND fetched_at LIKE ?""",
                (stock_code, field, f"{date}%"),
            ).fetchall()
            return [dict(row) for row in rows]

    def save_report(
        self,
        stock_code: str,
        mode: str,
        report_md: str,
        report_json: dict,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO reports (stock_code, mode, report_md, report_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    stock_code,
                    mode,
                    report_md,
                    json.dumps(report_json, ensure_ascii=False),
                    datetime.now().isoformat(),
                ),
            )
            return cursor.lastrowid

    def get_reports(self, stock_code: Optional[str] = None) -> list[dict]:
        with self._connect() as conn:
            if stock_code:
                rows = conn.execute(
                    "SELECT * FROM reports WHERE stock_code = ? ORDER BY created_at DESC",
                    (stock_code,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM reports ORDER BY created_at DESC"
                ).fetchall()
            return [dict(row) for row in rows]

    def delete_report(self, report_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))

    def save_setting(self, key: str, value: Any) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value, ensure_ascii=False)),
            )

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            if row:
                return json.loads(row["value"])
            return default

    def log_source(
        self,
        source: str,
        status: str,
        stock_code: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO source_logs (source, stock_code, status, message, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (source, stock_code, status, message or "", datetime.now().isoformat()),
            )
