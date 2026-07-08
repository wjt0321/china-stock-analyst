# china-stock-analyst 桌面端重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 `china-stock-analyst` Claude Code Skill 改造为基于 Tauri + Python Sidecar 的独立桌面端软件，保留 12 步专家链路与双轨评分体系，使用 Scrapling 多源抓取替代 Web Search，核心规则化、AI 仅作可选增强。

**Architecture:** Python Sidecar 负责数据采集（AKShare + Scrapling 多源）、交叉验证、规则化分析、报告生成和本地 SQLite 缓存；Tauri 前端通过 STDIN/STDOUT JSON Lines 与 Sidecar 通信，提供看板、分析向导、报告阅读器和设置页。

**Tech Stack:** Tauri 2.x, React/TypeScript, Python 3.10+, Scrapling, AKShare, SQLite, DeepSeek API (optional).

## Global Constraints

- **保持框架不变**：固定 12 步链路、8 位专家角色、双轨评分权重 40/35/25、最终标签 `可做/观察/回避`。
- **AI 边界**：核心评分与标签规则化；LLM 仅用于可选“增强解读”，默认关闭。
- **数据源平等**：AKShare 与网页源地位平等，多源交叉验证，多数投票/中位数/源优先级兜底。
- **Windows 优先**：Tauri + 内嵌 Python Sidecar，后续扩展到 macOS/Linux。
- **本地缓存**：SQLite 持久化自选股、原始数据、报告历史，支持离线回看。
- **合规**：仅抓取公开免费页面，控制频率，遵守 robots.txt。
- **测试驱动**：每个任务先写测试再实现，频繁提交。

---

## 文件结构总览

```text
china-stock-analyst/
├── desktop/                        # Python Sidecar
│   ├── pyproject.toml
│   ├── service.py                  # 进程入口、命令循环
│   ├── config_manager.py           # 配置读写
│   ├── storage.py                  # SQLite 封装
│   ├── data_fetcher.py             # 数据调度
│   ├── data_validator.py           # 多源标准化与冲突校验
│   ├── llm_adapter.py              # 可选 DeepSeek 增强
│   ├── report_renderer.py          # 报告渲染
│   ├── analysis_engine.py          # 规则化 12 步分析引擎
│   ├── scrapling_adapters/
│   │   ├── __init__.py
│   │   ├── base.py                 # BaseStockScraper 抽象
│   │   ├── eastmoney.py
│   │   ├── sina.py
│   │   ├── ths.py
│   │   └── tencent.py
│   └── tests/
│       ├── test_storage.py
│       ├── test_scrapling_adapters.py
│       ├── test_data_validator.py
│       ├── test_analysis_engine.py
│       └── test_service.py
├── src-tauri/                      # Tauri 应用
│   ├── src/
│   │   ├── main.rs
│   │   ├── sidecar.rs              # Sidecar 管理
│   │   └── commands.rs             # Tauri 命令
│   ├── capabilities/
│   ├── tauri.conf.json
│   ├── Cargo.toml
│   └── ui/                         # React 前端
│       ├── src/
│       │   ├── App.tsx
│       │   ├── pages/
│       │   │   ├── Dashboard.tsx
│       │   │   ├── Analyzer.tsx
│       │   │   ├── ReportViewer.tsx
│       │   │   └── Settings.tsx
│       │   ├── components/
│       │   │   ├── Watchlist.tsx
│       │   │   ├── ProgressSteps.tsx
│       │   │   └── ReportCard.tsx
│       │   └── api/
│       │       └── sidecar.ts      # Sidecar IPC 封装
│       ├── package.json
│       └── vite.config.ts
├── scripts/                        # 现有代码复用
│   ├── akshare_adapter.py
│   ├── technical_indicators.py
│   ├── backtest_framework.py
│   ├── stock_utils.py
│   ├── report_constants.py
│   └── ...
└── config/settings.json            # 兼容读取
```

---

## Phase 1: Python Sidecar 基础

### Task 1: 创建 `desktop/` 目录和依赖配置

**Files:**
- Create: `desktop/pyproject.toml`
- Create: `desktop/.python-version` (optional)
- Modify: `requirements.txt` (add desktop deps at root if needed)

**Interfaces:**
- Produces: `desktop/` package structure with dependencies.

- [ ] **Step 1: Create `desktop/pyproject.toml`**

```toml
[project]
name = "china-stock-analyst-desktop"
version = "0.1.0"
description = "Desktop sidecar for china-stock-analyst"
requires-python = ">=3.10"
dependencies = [
    "akshare>=1.18.0",
    "scrapling>=0.4.10",
    "pandas>=1.5.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "httpx>=0.24.0",
]
```

- [ ] **Step 2: Verify Python environment**

Run: `cd desktop && python -m pip install -e ".[dev]"`
Expected: installs successfully.

- [ ] **Step 3: Commit**

```bash
git add desktop/pyproject.toml
git commit -m "chore(desktop): add pyproject.toml and sidecar dependencies"
```

---

### Task 2: SQLite 存储层

**Files:**
- Create: `desktop/storage.py`
- Create: `desktop/tests/test_storage.py`

**Interfaces:**
- Produces:
  - `Storage(db_path: Path)` class
  - Methods: `init_schema()`, `save_watchlist_item(...)`, `get_watchlist()`, `save_raw_data(...)`, `get_raw_data(...)`, `save_report(...)`, `get_reports()`, `save_setting(...)`, `get_setting()`

- [ ] **Step 1: Write failing test**

```python
# desktop/tests/test_storage.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd desktop && pytest tests/test_storage.py -v`
Expected: `ModuleNotFoundError: No module named 'desktop.storage'`

- [ ] **Step 3: Implement `desktop/storage.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd desktop && pytest tests/test_storage.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desktop/storage.py desktop/tests/test_storage.py
git commit -m "feat(desktop): add SQLite storage layer"
```

---

### Task 3: 配置管理器

**Files:**
- Create: `desktop/config_manager.py`
- Create: `desktop/tests/test_config_manager.py`

**Interfaces:**
- Produces: `ConfigManager(storage: Storage, defaults_path: Path)`
- Methods: `get_source_priority()`, `get_llm_config()`, `get_analysis_config()`, `get(key, default)`

- [ ] **Step 1: Write failing test**

```python
# desktop/tests/test_config_manager.py
from pathlib import Path
from desktop.storage import Storage
from desktop.config_manager import ConfigManager


def test_source_priority_default(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.init_schema()
    cm = ConfigManager(storage, defaults_path=Path("nonexistent.json"))
    priority = cm.get_source_priority()
    assert priority[0] == "eastmoney"
```

- [ ] **Step 2: Implement `desktop/config_manager.py`**

```python
import json
from pathlib import Path
from typing import Any

from desktop.storage import Storage


DEFAULT_SOURCE_PRIORITY = ["eastmoney", "sina", "ths", "tencent", "akshare"]
DEFAULT_LLM_CONFIG = {
    "enabled": False,
    "provider": "deepseek",
    "base_url": "https://api.deepseek.com/v1",
    "api_key": "",
    "model": "deepseek-chat",
}
DEFAULT_ANALYSIS_CONFIG = {
    "short_term_weight": 0.40,
    "fundamental_weight": 0.35,
    "sentiment_weight": 0.25,
    "price_conflict_threshold": 0.01,
    "change_conflict_threshold": 0.012,
    "fund_flow_conflict_threshold": 0.35,
}


class ConfigManager:
    def __init__(self, storage: Storage, defaults_path: Path):
        self.storage = storage
        self.defaults_path = Path(defaults_path)
        self._defaults = self._load_file_defaults()
        self._init_defaults()

    def _load_file_defaults(self) -> dict:
        if self.defaults_path.exists():
            try:
                with self.defaults_path.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _init_defaults(self) -> None:
        if self.storage.get_setting("source_priority") is None:
            self.storage.save_setting(
                "source_priority",
                self._defaults.get("source_priority", DEFAULT_SOURCE_PRIORITY),
            )
        if self.storage.get_setting("llm_config") is None:
            self.storage.save_setting(
                "llm_config",
                self._defaults.get("llm", DEFAULT_LLM_CONFIG),
            )
        if self.storage.get_setting("analysis_config") is None:
            analysis = self._defaults.get("scoring", {})
            analysis.update(self._defaults.get("validation", {}))
            self.storage.save_setting(
                "analysis_config",
                {**DEFAULT_ANALYSIS_CONFIG, **analysis},
            )

    def get(self, key: str, default: Any = None) -> Any:
        return self.storage.get_setting(key, default)

    def set(self, key: str, value: Any) -> None:
        self.storage.save_setting(key, value)

    def get_source_priority(self) -> list[str]:
        return self.storage.get_setting("source_priority", DEFAULT_SOURCE_PRIORITY)

    def get_llm_config(self) -> dict:
        return self.storage.get_setting("llm_config", DEFAULT_LLM_CONFIG)

    def get_analysis_config(self) -> dict:
        return self.storage.get_setting("analysis_config", DEFAULT_ANALYSIS_CONFIG)
```

- [ ] **Step 3: Run test**

Run: `cd desktop && pytest tests/test_config_manager.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add desktop/config_manager.py desktop/tests/test_config_manager.py
git commit -m "feat(desktop): add config manager with defaults"
```

---

## Phase 2: 数据采集与 Scrapling 适配器

### Task 4: Scrapling 适配器基类

**Files:**
- Create: `desktop/scrapling_adapters/__init__.py`
- Create: `desktop/scrapling_adapters/base.py`
- Create: `desktop/tests/test_scrapling_base.py`

**Interfaces:**
- Produces: `BaseStockScraper` abstract class with `fetch_quote`, `fetch_news`, `fetch_fund_flow`.
- Produces: `QuoteSnapshot`, `NewsItem`, `FundFlow` dataclasses.

- [ ] **Step 1: Write failing test**

```python
# desktop/tests/test_scrapling_base.py
import pytest
from dataclasses import dataclass
from desktop.scrapling_adapters.base import BaseStockScraper, QuoteSnapshot


class DummyScraper(BaseStockScraper):
    name = "dummy"
    priority = 1
    enabled = True

    def fetch_quote(self, stock_code: str) -> QuoteSnapshot:
        return QuoteSnapshot(price=10.0, change=0.5, turnover=1000.0)


def test_dummy_scraper():
    s = DummyScraper()
    q = s.fetch_quote("600519")
    assert q.price == 10.0
```

- [ ] **Step 2: Implement `desktop/scrapling_adapters/base.py`**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class QuoteSnapshot:
    price: Optional[float] = None
    change: Optional[float] = None
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
```

- [ ] **Step 3: Run test**

Run: `cd desktop && pytest tests/test_scrapling_base.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add desktop/scrapling_adapters/
git commit -m "feat(desktop): add scrapling adapter base class"
```

---

### Task 5: 东方财富适配器

**Files:**
- Create: `desktop/scrapling_adapters/eastmoney.py`
- Create: `desktop/tests/test_eastmoney_adapter.py` (mock-based)

**Interfaces:**
- Produces: `EastmoneyScraper(BaseStockScraper)`
- Methods: `fetch_quote`, `fetch_news`, `fetch_fund_flow`

- [ ] **Step 1: Write failing test with mocked page**

```python
# desktop/tests/test_eastmoney_adapter.py
from unittest.mock import MagicMock, patch
from desktop.scrapling_adapters.eastmoney import EastmoneyScraper


def test_fetch_quote_parses_price():
    scraper = EastmoneyScraper()
    mock_page = MagicMock()
    mock_page.css_first.return_value.text = "10.50"
    with patch("scrapling.fetchers.StealthyFetcher.fetch", return_value=mock_page):
        quote = scraper.fetch_quote("600519")
    assert quote.price == 10.5
```

- [ ] **Step 2: Implement `desktop/scrapling_adapters/eastmoney.py`**

```python
import logging
from desktop.scrapling_adapters.base import BaseStockScraper, QuoteSnapshot, NewsItem, FundFlow

try:
    from scrapling.fetchers import StealthyFetcher
    _SCRAPLING_AVAILABLE = True
except ImportError:
    _SCRAPLING_AVAILABLE = False

LOGGER = logging.getLogger(__name__)


class EastmoneyScraper(BaseStockScraper):
    name = "eastmoney"
    priority = 1
    enabled = True
    _quote_url = "https://quote.eastmoney.com/concept/{code}.html"

    def __init__(self):
        self.fetcher = StealthyFetcher() if _SCRAPLING_AVAILABLE else None

    def fetch_quote(self, stock_code: str) -> QuoteSnapshot:
        if not self.fetcher:
            return QuoteSnapshot()
        url = f"https://quote.eastmoney.com/{stock_code}.html"
        try:
            page = self.fetcher.fetch(url, headless=True, network_idle=True)
            price_el = page.css_first(".price")
            change_el = page.css_first(".change")
            return QuoteSnapshot(
                price=_to_float(price_el.text if price_el else None),
                change=_to_float(change_el.text if change_el else None),
            )
        except Exception as e:
            LOGGER.error(f"Eastmoney fetch_quote failed: {e}")
            return QuoteSnapshot()

    def fetch_news(self, stock_code: str, limit: int = 10) -> list[NewsItem]:
        return []

    def fetch_fund_flow(self, stock_code: str) -> list[FundFlow]:
        return []


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None
```

- [ ] **Step 3: Run test**

Run: `cd desktop && pytest tests/test_eastmoney_adapter.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add desktop/scrapling_adapters/eastmoney.py desktop/tests/test_eastmoney_adapter.py
git commit -m "feat(desktop): add eastmoney scrapling adapter"
```

---

### Task 6: 新浪、同花顺、腾讯适配器

**Files:**
- Create: `desktop/scrapling_adapters/sina.py`
- Create: `desktop/scrapling_adapters/ths.py`
- Create: `desktop/scrapling_adapters/tencent.py`
- Create: `desktop/tests/test_scrapling_adapters.py`

**Interfaces:**
- Produces: `SinaScraper`, `ThsScraper`, `TencentScraper` following `BaseStockScraper`.

- [ ] **Step 1: Implement adapters**

Use the same pattern as Eastmoney, with appropriate URLs and selectors. Example for Sina:

```python
# desktop/scrapling_adapters/sina.py
import logging
from desktop.scrapling_adapters.base import BaseStockScraper, QuoteSnapshot

try:
    from scrapling.fetchers import StealthyFetcher
    _SCRAPLING_AVAILABLE = True
except ImportError:
    _SCRAPLING_AVAILABLE = False

LOGGER = logging.getLogger(__name__)


class SinaScraper(BaseStockScraper):
    name = "sina"
    priority = 2
    enabled = True

    def __init__(self):
        self.fetcher = StealthyFetcher() if _SCRAPLING_AVAILABLE else None

    def fetch_quote(self, stock_code: str) -> QuoteSnapshot:
        if not self.fetcher:
            return QuoteSnapshot()
        url = f"https://finance.sina.com.cn/realstock/company/{_sina_symbol(stock_code)}/nc.shtml"
        try:
            page = self.fetcher.fetch(url, headless=True, network_idle=True)
            price_el = page.css_first("#price")
            return QuoteSnapshot(price=_to_float(price_el.text if price_el else None))
        except Exception as e:
            LOGGER.error(f"Sina fetch_quote failed: {e}")
            return QuoteSnapshot()


def _sina_symbol(code: str) -> str:
    return f"sh{code}" if code.startswith("6") else f"sz{code}"


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None
```

Implement `ths.py` and `tencent.py` with appropriate URLs and selectors:

```python
# desktop/scrapling_adapters/ths.py
import logging
from desktop.scrapling_adapters.base import BaseStockScraper, QuoteSnapshot

try:
    from scrapling.fetchers import StealthyFetcher
    _SCRAPLING_AVAILABLE = True
except ImportError:
    _SCRAPLING_AVAILABLE = False

LOGGER = logging.getLogger(__name__)


class ThsScraper(BaseStockScraper):
    name = "ths"
    priority = 3
    enabled = True

    def __init__(self):
        self.fetcher = StealthyFetcher() if _SCRAPLING_AVAILABLE else None

    def fetch_quote(self, stock_code: str) -> QuoteSnapshot:
        if not self.fetcher:
            return QuoteSnapshot()
        url = f"https://basic.10jqka.com.cn/{stock_code}"
        try:
            page = self.fetcher.fetch(url, headless=True, network_idle=True)
            price_el = page.css_first(".price")
            return QuoteSnapshot(price=_to_float(price_el.text if price_el else None))
        except Exception as e:
            LOGGER.error(f"Ths fetch_quote failed: {e}")
            return QuoteSnapshot()


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None
```

```python
# desktop/scrapling_adapters/tencent.py
import logging
from desktop.scrapling_adapters.base import BaseStockScraper, QuoteSnapshot

try:
    from scrapling.fetchers import StealthyFetcher
    _SCRAPLING_AVAILABLE = True
except ImportError:
    _SCRAPLING_AVAILABLE = False

LOGGER = logging.getLogger(__name__)


class TencentScraper(BaseStockScraper):
    name = "tencent"
    priority = 4
    enabled = True

    def __init__(self):
        self.fetcher = StealthyFetcher() if _SCRAPLING_AVAILABLE else None

    def fetch_quote(self, stock_code: str) -> QuoteSnapshot:
        if not self.fetcher:
            return QuoteSnapshot()
        symbol = f"sh{stock_code}" if stock_code.startswith("6") else f"sz{stock_code}"
        url = f"https://qt.gtimg.cn/q={symbol}"
        try:
            page = self.fetcher.fetch(url, headless=True, network_idle=True)
            # Tencent quote API returns plain text; parse accordingly
            text = page.text or ""
            parts = text.split("~")
            if len(parts) > 3:
                return QuoteSnapshot(price=_to_float(parts[3]))
            return QuoteSnapshot()
        except Exception as e:
            LOGGER.error(f"Tencent fetch_quote failed: {e}")
            return QuoteSnapshot()


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None
```

- [ ] **Step 2: Write integration test**

```python
# desktop/tests/test_scrapling_adapters.py
from desktop.scrapling_adapters.eastmoney import EastmoneyScraper
from desktop.scrapling_adapters.sina import SinaScraper
from desktop.scrapling_adapters.ths import ThsScraper
from desktop.scrapling_adapters.tencent import TencentScraper


def test_all_adapters_have_required_interface():
    adapters = [EastmoneyScraper, SinaScraper, ThsScraper, TencentScraper]
    for cls in adapters:
        inst = cls()
        assert inst.name
        assert isinstance(inst.priority, int)
        assert hasattr(inst, "fetch_quote")
```

- [ ] **Step 3: Run tests**

Run: `cd desktop && pytest tests/test_scrapling_adapters.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add desktop/scrapling_adapters/sina.py desktop/scrapling_adapters/ths.py desktop/scrapling_adapters/tencent.py desktop/tests/test_scrapling_adapters.py
git commit -m "feat(desktop): add sina, ths, tencent scrapling adapters"
```

---

### Task 7: 数据调度器 `data_fetcher.py`

**Files:**
- Create: `desktop/data_fetcher.py`
- Create: `desktop/tests/test_data_fetcher.py`

**Interfaces:**
- Produces: `DataFetcher(config_manager, storage)`
- Method: `fetch(stock_code: str) -> dict` returns `{source_name: {field: value}}`

- [ ] **Step 1: Write failing test**

```python
# desktop/tests/test_data_fetcher.py
from unittest.mock import MagicMock
from desktop.data_fetcher import DataFetcher


def test_fetch_aggregates_sources():
    config = MagicMock()
    config.get_source_priority.return_value = ["eastmoney", "sina"]
    storage = MagicMock()
    fetcher = DataFetcher(config, storage)

    em = MagicMock()
    em.name = "eastmoney"
    em.fetch_quote.return_value = MagicMock(price=10.0, change=0.5)
    sina = MagicMock()
    sina.name = "sina"
    sina.fetch_quote.return_value = MagicMock(price=10.1, change=0.4)

    result = fetcher.fetch("600519", scrapers=[em, sina])
    assert "eastmoney" in result
    assert result["eastmoney"]["price"] == 10.0
```

- [ ] **Step 2: Implement `desktop/data_fetcher.py`**

```python
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
```

- [ ] **Step 3: Run test**

Run: `cd desktop && pytest tests/test_data_fetcher.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add desktop/data_fetcher.py desktop/tests/test_data_fetcher.py
git commit -m "feat(desktop): add data fetcher with akshare and scrapling sources"
```

---

### Task 8: 数据校验器 `data_validator.py`

**Files:**
- Create: `desktop/data_validator.py`
- Create: `desktop/tests/test_data_validator.py`

**Interfaces:**
- Produces: `DataValidator(config_manager)`
- Method: `validate(stock_code: str, raw_data: dict) -> ValidatedData`

- [ ] **Step 1: Write failing test**

```python
# desktop/tests/test_data_validator.py
from unittest.mock import MagicMock
from desktop.data_validator import DataValidator


def test_majority_vote_price():
    config = MagicMock()
    config.get_source_priority.return_value = ["eastmoney", "sina", "ths", "tencent", "akshare"]
    config.get_analysis_config.return_value = {
        "price_conflict_threshold": 0.01,
        "change_conflict_threshold": 0.012,
        "fund_flow_conflict_threshold": 0.35,
    }
    validator = DataValidator(config)
    raw = {
        "eastmoney": {"price": 10.0},
        "sina": {"price": 10.0},
        "ths": {"price": 10.01},
        "tencent": {"price": 10.5},
    }
    result = validator.validate("600519", raw)
    assert result["price"]["value"] == 10.0
    assert result["price"]["conflict"] is True
```

- [ ] **Step 2: Implement `desktop/data_validator.py`**

```python
import json
import statistics
from dataclasses import dataclass, field
from typing import Any

from desktop.config_manager import ConfigManager


@dataclass
class ValidatedField:
    value: Any = None
    sources: list[str] = field(default_factory=list)
    conflict: bool = False
    notes: list[str] = field(default_factory=list)


class DataValidator:
    def __init__(self, config: ConfigManager):
        self.config = config
        self.priority = config.get_source_priority()
        self.cfg = config.get_analysis_config()

    def validate(self, stock_code: str, raw_data: dict) -> dict[str, ValidatedField]:
        result: dict[str, ValidatedField] = {}

        numeric_fields = ["price", "change", "turnover"]
        for field in numeric_fields:
            values = []
            sources = []
            for source in self.priority:
                if source in raw_data and field in raw_data[source]:
                    v = raw_data[source][field]
                    if isinstance(v, (int, float)):
                        values.append((source, v))
                        sources.append(source)

            if not values:
                result[field] = ValidatedField(notes=["无有效数据源"])
                continue

            picked, method, conflict = self._resolve_numeric(values, field)
            notes = [f"来自 {len(values)} 个源", f"取值方式: {method}"]
            if conflict:
                notes.append("源间数值冲突")
            result[field] = ValidatedField(
                value=picked,
                sources=sources,
                conflict=conflict,
                notes=notes,
            )

        # Pass-through non-numeric data
        for source, fields in raw_data.items():
            for key in ["candles", "fund_flow", "news"]:
                if key in fields:
                    full_key = f"{source}_{key}"
                    result[full_key] = ValidatedField(
                        value=fields[key],
                        sources=[source],
                        conflict=False,
                    )

        return result

    def _resolve_numeric(self, values: list[tuple[str, float]], field: str) -> tuple[float, str, bool]:
        threshold = self.cfg.get(f"{field}_conflict_threshold", 0.01)
        if field == "change":
            threshold = self.cfg.get("change_conflict_threshold", 0.012)
        if field == "fund_flow":
            threshold = self.cfg.get("fund_flow_conflict_threshold", 0.35)

        # Round for voting
        rounded = [round(v, 2) for _, v in values]
        from collections import Counter
        counts = Counter(rounded)
        most_common, count = counts.most_common(1)[0]

        if count >= 2 and len(values) >= 3:
            return most_common, "majority_vote", False

        # Median
        sorted_vals = sorted([v for _, v in values])
        median = statistics.median(sorted_vals)

        # Conflict check
        if len(sorted_vals) >= 2:
            baseline = max(abs(median), 1.0)
            max_diff = max(abs(v - median) for v in sorted_vals) / baseline
            conflict = max_diff > threshold
        else:
            conflict = False

        # Priority fallback
        for source in self.priority:
            for src, val in values:
                if src == source:
                    return round(val, 2), "priority_fallback", conflict

        return round(median, 2), "median", conflict
```

- [ ] **Step 3: Run test**

Run: `cd desktop && pytest tests/test_data_validator.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add desktop/data_validator.py desktop/tests/test_data_validator.py
git commit -m "feat(desktop): add multi-source data validator"
```

---

## Phase 3: 规则化分析引擎

### Task 9: 规则化分析引擎骨架

**Files:**
- Create: `desktop/analysis_engine.py`
- Create: `desktop/tests/test_analysis_engine.py`
- Modify: `scripts/technical_indicators.py` (ensure callable from desktop)

**Interfaces:**
- Produces: `AnalysisEngine(config_manager)`
- Method: `analyze(stock_code: str, validated_data: dict) -> dict`
- Returns: full report JSON including audit, expert outputs, supervisor review, verdict.

- [ ] **Step 1: Write failing test**

```python
# desktop/tests/test_analysis_engine.py
from unittest.mock import MagicMock
from desktop.analysis_engine import AnalysisEngine


def test_analysis_engine_returns_verdict():
    config = MagicMock()
    config.get_analysis_config.return_value = {
        "short_term_weight": 0.40,
        "fundamental_weight": 0.35,
        "sentiment_weight": 0.25,
    }
    engine = AnalysisEngine(config)
    validated = {
        "price": {"value": 10.0, "conflict": False},
        "change": {"value": 2.5, "conflict": False},
        "akshare_candles": {"value": []},
    }
    report = engine.analyze("600519", validated)
    assert "verdict" in report
    assert report["verdict"] in ["可做", "观察", "回避"]
```

- [ ] **Step 2: Implement skeleton `desktop/analysis_engine.py`**

```python
import logging
from typing import Any

from desktop.config_manager import ConfigManager

LOGGER = logging.getLogger(__name__)


class AnalysisEngine:
    def __init__(self, config: ConfigManager):
        self.config = config
        self.cfg = config.get_analysis_config()

    def analyze(self, stock_code: str, validated_data: dict) -> dict:
        report = {
            "stock_code": stock_code,
            "audit_gate": self._run_data_auditor(validated_data),
            "expert_outputs": self._run_experts(validated_data),
            "expert_identity_gate": self._run_identity_gate(validated_data),
            "supervisor_review": {},
            "scoring": {},
            "verdict": "观察",
            "confidence": "中",
            "reasoning": [],
        }
        report["supervisor_review"] = self._run_supervisor_review(report)
        report["scoring"] = self._calculate_score(report)
        report["verdict"], report["confidence"] = self._derive_verdict(report)
        report["reasoning"] = self._build_reasoning(report)
        return report

    def _run_data_auditor(self, validated_data: dict) -> dict:
        # Expanded in Task 10
        return {"passed": True, "notes": []}

    def _run_experts(self, validated_data: dict) -> dict:
        return {
            "technical": self._technical_expert(validated_data),
            "fundamental": self._fundamental_expert(validated_data),
            "quant_flow": self._quant_flow_expert(validated_data),
            "risk": self._risk_expert(validated_data),
            "macro": self._macro_expert(validated_data),
            "industry": self._industry_expert(validated_data),
            "event": self._event_expert(validated_data),
        }

    def _technical_expert(self, validated_data: dict) -> dict:
        return {"view": "震荡", "decision_hint": "观察", "evidences": []}

    def _fundamental_expert(self, validated_data: dict) -> dict:
        return {"view": "中性", "decision_hint": "观察", "evidences": []}

    def _quant_flow_expert(self, validated_data: dict) -> dict:
        return {"view": "中性", "decision_hint": "观察", "evidences": []}

    def _risk_expert(self, validated_data: dict) -> dict:
        return {"view": "可控", "decision_hint": "观察", "evidences": []}

    def _macro_expert(self, validated_data: dict) -> dict:
        return {"view": "中性", "decision_hint": "观察", "evidences": []}

    def _industry_expert(self, validated_data: dict) -> dict:
        return {"view": "中性", "decision_hint": "观察", "evidences": []}

    def _event_expert(self, validated_data: dict) -> dict:
        return {"view": "中性", "decision_hint": "观察", "evidences": []}

    def _run_identity_gate(self, validated_data: dict) -> dict:
        return {"passed": True, "require_block": False, "notes": []}

    def _run_supervisor_review(self, report: dict) -> dict:
        return {"consensus": "观察", "conflict_items": []}

    def _calculate_score(self, report: dict) -> dict:
        return {"short_term": 50, "fundamental": 50, "risk": 50, "total": 50}

    def _derive_verdict(self, report: dict) -> tuple[str, str]:
        total = report["scoring"]["total"]
        if total >= 70:
            return "可做", "中"
        if total >= 50:
            return "观察", "中"
        return "回避", "低"

    def _build_reasoning(self, report: dict) -> list[str]:
        return ["基于当前数据综合评分得出"]
```

- [ ] **Step 3: Run test**

Run: `cd desktop && pytest tests/test_analysis_engine.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add desktop/analysis_engine.py desktop/tests/test_analysis_engine.py
git commit -m "feat(desktop): add analysis engine skeleton"
```

---

### Task 10: 技术指标与评分规则落地

**Files:**
- Modify: `desktop/analysis_engine.py`
- Modify: `desktop/tests/test_analysis_engine.py`
- Reuse: `scripts/technical_indicators.py`

**Interfaces:**
- Produces: Real technical/fundamental/quant/risk scoring logic.

- [ ] **Step 1: Add technical scoring**

Update `_technical_expert` to use `calc_full_indicators` from `scripts.technical_indicators`:

```python
from scripts.technical_indicators import calc_full_indicators


def _technical_expert(self, validated_data: dict) -> dict:
    candles = validated_data.get("akshare_candles", {}).get("value", [])
    if not candles or len(candles) < 20:
        return {"view": "数据不足", "decision_hint": "观察", "evidences": ["K线数据不足"]}

    indicators = calc_full_indicators(candles)
    price = validated_data.get("price", {}).get("value")
    vwap = indicators.get("vwap")
    rsi = indicators.get("rsi")
    atr = indicators.get("atr")

    hints = []
    if price and vwap:
        deviation = (price - vwap) / vwap
        if deviation > 0.02:
            hints.append("价格高于 VWAP，短线偏强")
        elif deviation < -0.02:
            hints.append("价格低于 VWAP，短线偏弱")

    decision = "观察"
    if rsi is not None:
        if rsi > 70:
            decision = "回避"
        elif rsi < 30:
            decision = "可做"

    return {
        "view": "多头" if decision == "可做" else "空头" if decision == "回避" else "震荡",
        "decision_hint": decision,
        "indicators": {"vwap": vwap, "rsi": rsi, "atr": atr},
        "evidences": hints,
    }
```

- [ ] **Step 2: Add scoring weights**

```python
def _calculate_score(self, report: dict) -> dict:
    cfg = self.cfg
    technical_hint = report["expert_outputs"]["technical"]["decision_hint"]
    quant_hint = report["expert_outputs"]["quant_flow"]["decision_hint"]

    short_term = self._hint_to_score(technical_hint) * 0.5 + self._hint_to_score(quant_hint) * 0.5
    fundamental = self._hint_to_score(report["expert_outputs"]["fundamental"]["decision_hint"])
    risk = self._hint_to_score(report["expert_outputs"]["risk"]["decision_hint"])

    total = (
        short_term * cfg["short_term_weight"]
        + fundamental * cfg["fundamental_weight"]
        + risk * cfg["sentiment_weight"]
    )
    return {"short_term": short_term, "fundamental": fundamental, "risk": risk, "total": round(total, 2)}


def _hint_to_score(self, hint: str) -> float:
    mapping = {"可做": 80, "观察": 55, "回避": 30, "数据不足": 50, "中性": 55}
    return mapping.get(hint, 50)
```

- [ ] **Step 3: Add tests**

```python
def test_technical_expert_with_candles():
    config = MagicMock()
    config.get_analysis_config.return_value = {
        "short_term_weight": 0.40,
        "fundamental_weight": 0.35,
        "sentiment_weight": 0.25,
    }
    engine = AnalysisEngine(config)
    candles = [
        {"date": "2026-07-0%d" % i, "open": 9.0, "high": 10.0, "low": 8.5, "close": 9.5 + i * 0.1, "volume": 1000}
        for i in range(1, 25)
    ]
    validated = {"price": {"value": 11.0}, "akshare_candles": {"value": candles}}
    report = engine.analyze("600519", validated)
    assert report["expert_outputs"]["technical"]["decision_hint"] in ["可做", "观察", "回避"]
```

- [ ] **Step 4: Run tests**

Run: `cd desktop && pytest tests/test_analysis_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add desktop/analysis_engine.py desktop/tests/test_analysis_engine.py
git commit -m "feat(desktop): add technical indicators and scoring rules"
```

---

### Task 11: 报告渲染器

**Files:**
- Create: `desktop/report_renderer.py`
- Create: `desktop/tests/test_report_renderer.py`

**Interfaces:**
- Produces: `ReportRenderer()`
- Method: `render(report_json: dict) -> str` returns Markdown.

- [ ] **Step 1: Write failing test**

```python
# desktop/tests/test_report_renderer.py
from desktop.report_renderer import ReportRenderer


def test_render_markdown():
    renderer = ReportRenderer()
    report = {
        "stock_code": "600519",
        "verdict": "观察",
        "confidence": "中",
        "scoring": {"total": 55},
    }
    md = renderer.render(report)
    assert "600519" in md
    assert "观察" in md
```

- [ ] **Step 2: Implement `desktop/report_renderer.py`**

```python
from datetime import datetime


class ReportRenderer:
    def render(self, report: dict) -> str:
        lines = [
            f"# {report['stock_code']} 短线分析报告",
            "",
            f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- **最终标签**: {report['verdict']}",
            f"- **置信度**: {report['confidence']}",
            f"- **综合评分**: {report.get('scoring', {}).get('total', 'N/A')}",
            "",
            "## 专家观点",
            "",
        ]
        for expert, output in report.get("expert_outputs", {}).items():
            lines.append(f"### {expert}")
            lines.append(f"- 观点: {output.get('view', 'N/A')}")
            lines.append(f"- 建议: {output.get('decision_hint', 'N/A')}")
            evidences = output.get("evidences", [])
            if evidences:
                lines.append("- 依据:")
                for ev in evidences:
                    lines.append(f"  - {ev}")
            lines.append("")

        lines.append("## 推理过程")
        for reason in report.get("reasoning", []):
            lines.append(f"- {reason}")
        lines.append("")
        lines.append("> 免责声明：所有分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。")
        return "\n".join(lines)
```

- [ ] **Step 3: Run test**

Run: `cd desktop && pytest tests/test_report_renderer.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add desktop/report_renderer.py desktop/tests/test_report_renderer.py
git commit -m "feat(desktop): add markdown report renderer"
```

---

## Phase 4: Sidecar 服务与 LLM 适配器

### Task 12: LLM 适配器（可选 DeepSeek）

**Files:**
- Create: `desktop/llm_adapter.py`
- Create: `desktop/tests/test_llm_adapter.py`

**Interfaces:**
- Produces: `LLMAdapter(config_manager)`
- Method: `enhance(report_json: dict) -> str | None`

- [ ] **Step 1: Write failing test**

```python
# desktop/tests/test_llm_adapter.py
from unittest.mock import MagicMock, patch
from desktop.llm_adapter import LLMAdapter


def test_llm_disabled_returns_none():
    config = MagicMock()
    config.get_llm_config.return_value = {"enabled": False}
    adapter = LLMAdapter(config)
    assert adapter.enhance({}) is None


def test_llm_with_mock_response():
    config = MagicMock()
    config.get_llm_config.return_value = {
        "enabled": True,
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "test-key",
        "model": "deepseek-chat",
    }
    adapter = LLMAdapter(config)
    with patch("httpx.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "增强解读"}}]
        }
        result = adapter.enhance({"stock_code": "600519", "verdict": "观察"})
    assert result == "增强解读"
```

- [ ] **Step 2: Implement `desktop/llm_adapter.py`**

```python
import json
import logging

import httpx

from desktop.config_manager import ConfigManager

LOGGER = logging.getLogger(__name__)


class LLMAdapter:
    def __init__(self, config: ConfigManager):
        self.config = config
        self.cfg = config.get_llm_config()

    def enhance(self, report_json: dict) -> str | None:
        if not self.cfg.get("enabled"):
            return None
        api_key = self.cfg.get("api_key", "")
        if not api_key:
            return None

        url = f"{self.cfg.get('base_url', 'https://api.deepseek.com/v1')}/chat/completions"
        prompt = self._build_prompt(report_json)

        try:
            response = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.cfg.get("model", "deepseek-chat"),
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是 A 股分析助手。请严格基于下面提供的事实数据生成解读，禁止编造价格、资金流或任何未提供的数据。",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            LOGGER.error(f"LLM enhancement failed: {e}")
            return None

    def _build_prompt(self, report_json: dict) -> str:
        return f"""请基于以下已验证的分析报告生成一段简洁的增强解读（200字以内），说明核心逻辑和风险点：

```json
{json.dumps(report_json, ensure_ascii=False, indent=2)}
```
"""
```

- [ ] **Step 3: Run test**

Run: `cd desktop && pytest tests/test_llm_adapter.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add desktop/llm_adapter.py desktop/tests/test_llm_adapter.py
git commit -m "feat(desktop): add optional DeepSeek LLM enhancement adapter"
```

---

### Task 13: Sidecar 命令循环服务

**Files:**
- Create: `desktop/service.py`
- Create: `desktop/tests/test_service.py`

**Interfaces:**
- Produces: `service.py` CLI entry that reads JSON Lines from stdin, writes JSON Lines to stdout.
- Commands: `analyze`, `watchlist`, `settings`, `reports`.

- [ ] **Step 1: Write failing test**

```python
# desktop/tests/test_service.py
import json
from unittest.mock import MagicMock, patch
from desktop.service import Service


def test_service_handle_analyze():
    storage = MagicMock()
    storage.init_schema = MagicMock()
    config = MagicMock()
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

    service = Service(storage, config, fetcher, validator, engine, renderer, llm)
    cmd = {"cmd": "analyze", "codes": ["600519"], "mode": "single", "request_id": "r1"}
    result = service.handle(cmd)
    assert result["status"] == "success"
    assert result["request_id"] == "r1"
```

- [ ] **Step 2: Implement `desktop/service.py`**

```python
import json
import logging
import sys
from pathlib import Path
from typing import Any

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
            self.config.set(cmd["key"], cmd["value"])
            return {"status": "success", "request_id": request_id}
        return {"status": "error", "error_code": "INVALID_SETTINGS_ACTION", "request_id": request_id}


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
```

- [ ] **Step 3: Run test**

Run: `cd desktop && pytest tests/test_service.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add desktop/service.py desktop/tests/test_service.py
git commit -m "feat(desktop): add JSON Lines sidecar service"
```

---

## Phase 5: Tauri 前端

### Task 14: Tauri 项目初始化

**Files:**
- Create: `src-tauri/` directory
- Create: `src-tauri/Cargo.toml`
- Create: `src-tauri/tauri.conf.json`
- Create: `src-tauri/src/main.rs`
- Create: `src-tauri/ui/package.json`

**Interfaces:**
- Produces: Runnable Tauri app shell.

- [ ] **Step 1: Initialize Tauri project**

Run:

```bash
# Ensure Node.js and Rust are installed
npm create tauri-app@latest src-tauri -- --template vanilla-ts --manager npm --before-dev-command "" --before-build-command ""
```

For this plan, assume the standard Tauri 2 structure. Then adjust to place the frontend under `src-tauri/ui/`.

- [ ] **Step 2: Configure `src-tauri/tauri.conf.json`**

```json
{
  "identifier": "com.wxbfnnas.china-stock-analyst",
  "productName": "A股智能分析助手",
  "version": "0.1.0",
  "build": {
    "frontendDist": "../ui/dist",
    "devUrl": "http://localhost:5173",
    "beforeDevCommand": "cd ui && npm run dev",
    "beforeBuildCommand": "cd ui && npm run build"
  },
  "app": {
    "windows": [
      {
        "title": "A股智能分析助手",
        "width": 1280,
        "height": 800,
        "resizable": true
      }
    ]
  },
  "bundle": {
    "active": true,
    "targets": ["msi", "nsis"],
    "icon": ["icons/icon.ico"]
  }
}
```

- [ ] **Step 3: Configure `src-tauri/Cargo.toml`**

```toml
[package]
name = "china-stock-analyst-desktop"
version = "0.1.0"
edition = "2021"

[dependencies]
tauri = { version = "2.0", features = ["shell-sidecar"] }
tauri-plugin-shell = "2.0"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tokio = { version = "1", features = ["full"] }

[features]
default = ["custom-protocol"]
custom-protocol = ["tauri/custom-protocol"]
```

- [ ] **Step 4: Basic `src-tauri/src/main.rs`**

```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod sidecar;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            sidecar::spawn_sidecar(app)?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![sidecar::send_command])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 5: Commit**

```bash
git add src-tauri/
git commit -m "feat(tauri): initialize tauri project shell"
```

---

### Task 15: Sidecar 管理（Rust）

**Files:**
- Create: `src-tauri/src/sidecar.rs`

**Interfaces:**
- Produces: `spawn_sidecar(app)` and `send_command(command: String) -> Result<String, String>`.

- [ ] **Step 1: Implement sidecar management**

```rust
use std::io::Write;
use std::process::Stdio;
use std::sync::Mutex;
use tauri::{AppHandle, Manager, State};
use tauri_plugin_shell::ShellExt;

pub struct SidecarState {
    pub stdin: Mutex<std::process::ChildStdin>,
    pub output: Mutex<String>,
}

pub fn spawn_sidecar(app: &AppHandle) -> Result<(), String> {
    let sidecar_command = app
        .shell()
        .sidecar("python")
        .map_err(|e| e.to_string())?;

    let mut child = sidecar_command
        .arg("desktop/service.py")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| e.to_string())?;

    let stdin = child.stdin.take().ok_or("Failed to open sidecar stdin")?;
    let stdout = child.stdout.take().ok_or("Failed to open sidecar stdout")?;

    app.manage(SidecarState {
        stdin: Mutex::new(stdin),
        output: Mutex::new(String::new()),
    });

    // Spawn stdout reader
    let app_clone = app.clone();
    std::thread::spawn(move || {
        let reader = std::io::BufReader::new(stdout);
        use std::io::BufRead;
        for line in reader.lines() {
            if let Ok(line) = line {
                if let Some(state) = app_clone.try_state::<SidecarState>() {
                    if let Ok(mut output) = state.output.lock() {
                        output.push_str(&line);
                        output.push('\n');
                    }
                }
            }
        }
    });

    Ok(())
}

#[tauri::command]
pub fn send_command(state: State<'_, SidecarState>, command: String) -> Result<String, String> {
    let mut stdin = state.stdin.lock().map_err(|e| e.to_string())?;
    writeln!(stdin, "{}", command).map_err(|e| e.to_string())?;
    stdin.flush().map_err(|e| e.to_string())?;

    // Simple synchronous read: wait for one line of output
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(60);
    loop {
        if std::time::Instant::now() > deadline {
            return Err("Sidecar response timeout".to_string());
        }
        {
            let output = state.output.lock().map_err(|e| e.to_string())?;
            if !output.is_empty() {
                let mut lines: Vec<&str> = output.lines().collect();
                if let Some(line) = lines.pop() {
                    // Note: real implementation needs proper line queue, this is illustrative
                    return Ok(line.to_string());
                }
            }
        }
        std::thread::sleep(std::time::Duration::from_millis(50));
    }
}
```

- [ ] **Step 2: Add build config for sidecar**

In `src-tauri/tauri.conf.json`, add:

```json
"bundle": {
  "externalBin": ["python"]
}
```

And create `src-tauri/sidecars/python.exe` placeholder or build script to bundle Python.

- [ ] **Step 3: Commit**

```bash
git add src-tauri/src/sidecar.rs
git commit -m "feat(tauri): add python sidecar spawning and command relay"
```

---

### Task 16: 前端页面（React + TypeScript）

**Files:**
- Create: `src-tauri/ui/package.json`
- Create: `src-tauri/ui/src/App.tsx`
- Create: `src-tauri/ui/src/pages/Dashboard.tsx`
- Create: `src-tauri/ui/src/pages/Analyzer.tsx`
- Create: `src-tauri/ui/src/pages/ReportViewer.tsx`
- Create: `src-tauri/ui/src/pages/Settings.tsx`
- Create: `src-tauri/ui/src/api/sidecar.ts`

**Interfaces:**
- Produces: SPA with routing, sidecar IPC wrapper.

- [ ] **Step 1: Create `src-tauri/ui/package.json`**

```json
{
  "name": "china-stock-analyst-ui",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.24.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.5.0",
    "vite": "^5.3.0"
  }
}
```

- [ ] **Step 2: Create sidecar API wrapper**

```typescript
// src-tauri/ui/src/api/sidecar.ts
import { invoke } from "@tauri-apps/api/core";

export async function sendCommand<T = unknown>(cmd: object): Promise<T> {
  const response = await invoke<string>("send_command", {
    command: JSON.stringify(cmd),
  });
  return JSON.parse(response) as T;
}

export async function analyzeStock(codes: string[], mode: string = "single") {
  return sendCommand({
    cmd: "analyze",
    codes,
    mode,
    request_id: crypto.randomUUID(),
  });
}

export async function getWatchlist() {
  return sendCommand({ cmd: "watchlist", request_id: crypto.randomUUID() });
}

export async function getSettings() {
  return sendCommand({ cmd: "settings", action: "get", request_id: crypto.randomUUID() });
}
```

- [ ] **Step 3: Create Dashboard page**

```tsx
// src-tauri/ui/src/pages/Dashboard.tsx
import { useEffect, useState } from "react";
import { getWatchlist, analyzeStock } from "../api/sidecar";

export default function Dashboard() {
  const [watchlist, setWatchlist] = useState<any[]>([]);

  useEffect(() => {
    getWatchlist().then((res: any) => setWatchlist(res.data || []));
  }, []);

  return (
    <div>
      <h1>自选股看板</h1>
      <ul>
        {watchlist.map((item) => (
          <li key={item.stock_code}>
            {item.stock_code} {item.stock_name}
            <button onClick={() => analyzeStock([item.stock_code])}>分析</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: Create Analyzer page**

```tsx
// src-tauri/ui/src/pages/Analyzer.tsx
import { useState } from "react";
import { analyzeStock } from "../api/sidecar";

export default function Analyzer() {
  const [codes, setCodes] = useState("600519");
  const [result, setResult] = useState<any>(null);

  const handleAnalyze = async () => {
    const list = codes.split(/[,，\s]+/).filter(Boolean);
    const res = await analyzeStock(list, list.length > 1 ? "compare" : "single");
    setResult(res);
  };

  return (
    <div>
      <h1>分析向导</h1>
      <input value={codes} onChange={(e) => setCodes(e.target.value)} />
      <button onClick={handleAnalyze}>开始分析</button>
      {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
    </div>
  );
}
```

- [ ] **Step 5: Create App.tsx with routing**

```tsx
// src-tauri/ui/src/App.tsx
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Analyzer from "./pages/Analyzer";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <BrowserRouter>
      <nav>
        <Link to="/">看板</Link> | <Link to="/analyze">分析</Link> | <Link to="/settings">设置</Link>
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/analyze" element={<Analyzer />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 6: Run dev server**

Run: `cd src-tauri/ui && npm install && npm run dev`
Expected: Vite dev server starts on `http://localhost:5173`.

- [ ] **Step 7: Commit**

```bash
git add src-tauri/ui/
git commit -m "feat(tauri): add react frontend pages and sidecar api wrapper"
```

---

### Task 17: 设置页与报告阅读器

**Files:**
- Create: `src-tauri/ui/src/pages/Settings.tsx`
- Create: `src-tauri/ui/src/pages/ReportViewer.tsx`
- Modify: `src-tauri/ui/src/App.tsx`

**Interfaces:**
- Produces: Settings form for source priority and LLM config; Markdown report viewer.

- [ ] **Step 1: Implement Settings page**

```tsx
// src-tauri/ui/src/pages/Settings.tsx
import { useEffect, useState } from "react";
import { getSettings, sendCommand } from "../api/sidecar";

export default function Settings() {
  const [llmKey, setLlmKey] = useState("");

  useEffect(() => {
    getSettings().then((res: any) => {
      setLlmKey(res.data?.llm_config?.api_key || "");
    });
  }, []);

  const save = async () => {
    await sendCommand({
      cmd: "settings",
      action: "set",
      key: "llm_config",
      value: { enabled: Boolean(llmKey), api_key: llmKey, provider: "deepseek" },
      request_id: crypto.randomUUID(),
    });
    alert("已保存");
  };

  return (
    <div>
      <h1>设置</h1>
      <label>
        DeepSeek API Key:
        <input type="password" value={llmKey} onChange={(e) => setLlmKey(e.target.value)} />
      </label>
      <button onClick={save}>保存</button>
    </div>
  );
}
```

- [ ] **Step 2: Implement ReportViewer page**

```tsx
// src-tauri/ui/src/pages/ReportViewer.tsx
export default function ReportViewer({ report }: { report: any }) {
  if (!report) return null;
  return (
    <div className="report">
      <pre>{report.report_md}</pre>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add src-tauri/ui/src/pages/Settings.tsx src-tauri/ui/src/pages/ReportViewer.tsx
git commit -m "feat(tauri): add settings and report viewer pages"
```

---

## Phase 6: 打包、集成测试与发布

### Task 18: Python 打包脚本

**Files:**
- Create: `scripts/build_sidecar.py`
- Create: `scripts/requirements-desktop.txt`

**Interfaces:**
- Produces: A `python/` directory or executable containing Python runtime + dependencies.

- [ ] **Step 1: Create requirements file**

```text
# scripts/requirements-desktop.txt
akshare>=1.18.0
scrapling>=1.0.0
pandas>=1.5.0
httpx>=0.24.0
pytest>=7.0.0
```

- [ ] **Step 2: Create build script**

```python
# scripts/build_sidecar.py
import subprocess
import sys
from pathlib import Path


def main():
    target = Path("src-tauri/sidecars/python")
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            "scripts/requirements-desktop.txt",
            "--target",
            str(target / "Lib" / "site-packages"),
        ],
        check=True,
    )
    print(f"Sidecar Python environment prepared at {target}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run build script**

Run: `python scripts/build_sidecar.py`
Expected: dependencies installed into `src-tauri/sidecars/python/`.

- [ ] **Step 4: Commit**

```bash
git add scripts/build_sidecar.py scripts/requirements-desktop.txt
git commit -m "chore(build): add python sidecar packaging script"
```

---

### Task 19: Tauri 构建与安装包

**Files:**
- Modify: `src-tauri/tauri.conf.json`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `.msi` installer for Windows.

- [ ] **Step 1: Add build ignore rules**

Add to `.gitignore`:

```gitignore
# Tauri build outputs
src-tauri/target/
src-tauri/ui/dist/
src-tauri/sidecars/python/
data/
desktop.log
```

- [ ] **Step 2: Build Tauri app**

Run:

```bash
cd src-tauri
cargo tauri build
```

Expected: produces `src-tauri/target/release/bundle/msi/*.msi`.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore(build): add tauri build artifacts to gitignore"
```

---

### Task 20: 端到端集成测试

**Files:**
- Create: `desktop/tests/test_integration.py`

**Interfaces:**
- Produces: Integration test covering full analyze pipeline.

- [ ] **Step 1: Write integration test**

```python
# desktop/tests/test_integration.py
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
```

- [ ] **Step 2: Run integration test**

Run: `cd desktop && pytest tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add desktop/tests/test_integration.py
git commit -m "test(desktop): add end-to-end integration test"
```

---

### Task 21: 文档更新与最终验收

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md` (if needed)

**Interfaces:**
- Produces: Updated project documentation.

- [ ] **Step 1: Update README.md desktop section**

Add section:

```markdown
## 桌面端

项目已支持 Tauri + Python Sidecar 桌面端，详见：
- 设计文档：`docs/superpowers/specs/2026-07-08-desktop-app-design.md`
- 实施计划：`docs/superpowers/plans/2026-07-08-desktop-app-implementation-plan.md`

### 开发运行

```bash
cd src-tauri/ui && npm install && npm run dev
cd desktop && pip install -e ".[dev]"
```

### 打包

```bash
python scripts/build_sidecar.py
cd src-tauri && cargo tauri build
```
```

- [ ] **Step 2: Run full test suite**

Run:

```bash
python -m pytest tests/ -v
cd desktop && python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README with desktop app instructions"
```

---

## 执行顺序总结

```text
Phase 1: 基础
  Task 1 → Task 2 → Task 3
Phase 2: 数据
  Task 4 → Task 5 → Task 6 → Task 7 → Task 8
Phase 3: 分析
  Task 9 → Task 10 → Task 11
Phase 4: 服务
  Task 12 → Task 13
Phase 5: 前端
  Task 14 → Task 15 → Task 16 → Task 17
Phase 6: 打包
  Task 18 → Task 19 → Task 20 → Task 21
```

每个 Task 内部按“写测试 → 跑测试（失败）→ 实现 → 跑测试（通过）→ 提交”执行。
