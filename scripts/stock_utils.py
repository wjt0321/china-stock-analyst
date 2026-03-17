# A股分析辅助脚本
# 关键字段主来源为 AKShare，Web 检索仅用于资讯补充

# 股票代码正则验证
import json
import importlib
import logging
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


STOCK_NAME_ALIAS_MAP = {
    "浦发银行": ["上海浦东发展银行", "浦发"],
    "招商银行": ["招行"],
    "中国能建": ["中国能源建设", "中国能源建设股份有限公司"],
    "首开股份": ["首开", "北京首都开发股份有限公司"],
    "晋控电力": ["山西晋控电力", "晋能控股电力"],
}

LOGGER = logging.getLogger(__name__)
EASTMONEY_APIKEY_ENV = "EASTMONEY_APIKEY"
_SKILL_ROOT = Path(__file__).resolve().parents[1]
_ENV_FILE_CANDIDATES = (".env.local", ".env")
DEFAULT_EASTMONEY_BASE_URL = "https://mkapi2.dfcfs.com/finskillshub/api/claw"
DEFAULT_EASTMONEY_ENDPOINT_NEWS_SEARCH = "/news-search"
DEFAULT_EASTMONEY_ENDPOINT_QUERY = "/query"
DEFAULT_EASTMONEY_ENDPOINT_STOCK_SCREEN = "/stock-screen"
EASTMONEY_BASE_URL = os.getenv("EASTMONEY_BASE_URL", DEFAULT_EASTMONEY_BASE_URL)
EASTMONEY_ENDPOINT_NEWS_SEARCH = os.getenv("EASTMONEY_ENDPOINT_NEWS_SEARCH", DEFAULT_EASTMONEY_ENDPOINT_NEWS_SEARCH)
EASTMONEY_ENDPOINT_QUERY = os.getenv("EASTMONEY_ENDPOINT_QUERY", DEFAULT_EASTMONEY_ENDPOINT_QUERY)
EASTMONEY_ENDPOINT_STOCK_SCREEN = os.getenv("EASTMONEY_ENDPOINT_STOCK_SCREEN", DEFAULT_EASTMONEY_ENDPOINT_STOCK_SCREEN)
EASTMONEY_DAILY_LIMIT = 50
_EASTMONEY_COUNTER_FILE = Path(__file__).resolve().parent / ".eastmoney_daily_counter.json"
_EASTMONEY_COUNTER_LOCK = threading.Lock()
EASTMONEY_EMPTY_RESULT_TIP = (
    "东方财富返回空结果：请缩小时间范围、补充股票代码或改用更具体关键词后重试；"
    "如仍无结果，可前往东方财富妙想AI继续检索。"
)
EASTMONEY_BLOCKED_RESULT_TIP = "查询范围过大，已触发保护性拦截。请缩小时间区间、提高筛选条件约束或降低返回条数。"
EASTMONEY_STOCK_SCREEN_COLUMN_MAP = {
    "code": "股票代码",
    "symbol": "股票代码",
    "stock_code": "股票代码",
    "secu_code": "股票代码",
    "security_code": "股票代码",
    "name": "股票名称",
    "stock_name": "股票名称",
    "secu_name": "股票名称",
    "security_name": "股票名称",
    "latest_price": "最新价",
    "price": "最新价",
    "change_pct": "涨跌幅",
    "pct_chg": "涨跌幅",
    "turnover_rate": "换手率",
    "volume_ratio": "量比",
    "main_net_inflow": "主力净流入",
    "pe_ttm": "市盈率TTM",
    "market_cap": "总市值",
    "sort_value": "排序值",
    "score": "排序值",
}

AKSHARE_MODULE_NAME = "akshare"
STANDARD_ERROR_CODE_INVALID_ARGUMENT = "INVALID_ARGUMENT"
STANDARD_ERROR_CODE_AKSHARE_NOT_INSTALLED = "AKSHARE_NOT_INSTALLED"
STANDARD_ERROR_CODE_AKSHARE_API_ERROR = "AKSHARE_API_ERROR"
STANDARD_ERROR_CODE_DATA_EMPTY = "DATA_EMPTY"
STANDARD_ERROR_CODE_DATA_SCHEMA_ERROR = "DATA_SCHEMA_ERROR"
STANDARD_ERROR_CODE_INTERNAL_ERROR = "INTERNAL_ERROR"
AKSHARE_SECURITY_FIELD_ALIASES = {
    "symbol": ["代码", "股票代码", "symbol", "code"],
    "name": ["名称", "股票简称", "stock_name", "name"],
    "market": ["市场", "市场类型", "market"],
    "trade_date": ["交易日期", "交易日", "日期", "更新时间", "trade_date", "date", "time"],
    "last_price": ["最新价", "现价", "last_price", "price"],
    "change_percent": ["涨跌幅", "change_percent", "pct_chg"],
    "turnover_rate": ["换手率", "turnover_rate"],
    "volume_ratio": ["量比", "volume_ratio"],
    "pe_ttm": ["市盈率-动态", "市盈率TTM", "pe_ttm"],
    "pb": ["市净率", "pb"],
    "amount": ["成交额", "amount"],
    "volume": ["成交量", "volume"],
}
QUERY_KEY_FIELD_SOURCE_PRIORITY = [
    {"provider": "akshare", "priority": 1, "scope": "key_fields"},
    {"provider": "eastmoney_query", "priority": 2, "scope": "query_fallback"},
    {"provider": "web_search", "priority": 3, "scope": "news_supplement_only"},
]
AKSHARE_QUERY_FIELD_MAP = {
    "price": "last_price",
    "latest_price": "last_price",
    "last_price": "last_price",
    "change": "change_percent",
    "change_percent": "change_percent",
    "change_pct": "change_percent",
    "pct_chg": "change_percent",
    "turnover_rate": "turnover_rate",
    "volume_ratio": "volume_ratio",
    "pe_ttm": "pe_ttm",
    "pb": "pb",
    "amount": "amount",
    "volume": "volume",
    "stock_code": "symbol",
    "code": "symbol",
    "symbol": "symbol",
    "stock_name": "name",
    "name": "name",
    "market": "market",
}


class EastmoneyPostError(RuntimeError):
    """东财 POST 请求异常基类"""


class EastmoneyApiKeyMissingError(EastmoneyPostError):
    """未读取到 EASTMONEY_APIKEY"""


class EastmoneyDailyLimitError(EastmoneyPostError):
    """超过 50 次/日配额"""


class EastmoneyHttpError(EastmoneyPostError):
    """HTTP 请求异常"""


class EastmoneyDecodeError(EastmoneyPostError):
    """响应解析异常"""


def _build_standard_result(data: Any = None, meta: dict = None) -> dict:
    return {
        "success": True,
        "error": {},
        "meta": _as_dict(meta),
        "data": data if data is not None else {},
    }


def _build_standard_error(
    code: str,
    message: str,
    retryable: bool = False,
    details: Any = None,
    meta: dict = None,
) -> dict:
    return {
        "success": False,
        "error": {
            "code": str(code or STANDARD_ERROR_CODE_INTERNAL_ERROR),
            "message": str(message or "未知错误"),
            "retryable": bool(retryable),
            "details": details if details is not None else {},
        },
        "meta": _as_dict(meta),
        "data": {},
    }


def _get_value_by_alias(record: dict, aliases: list, default: Any = "") -> Any:
    if not isinstance(record, dict):
        return default
    for key in aliases:
        if key in record and record.get(key) not in (None, ""):
            return record.get(key)
    return default


def _safe_number(value: Any) -> Any:
    if value in (None, ""):
        return ""
    text = str(value).replace(",", "").strip()
    try:
        return float(text)
    except (TypeError, ValueError):
        return value


def _safe_records(dataset: Any) -> list:
    if dataset is None:
        return []
    if isinstance(dataset, list):
        return [item for item in dataset if isinstance(item, dict)]
    if isinstance(dataset, dict):
        return [dataset]
    to_dict_fn = getattr(dataset, "to_dict", None)
    if callable(to_dict_fn):
        try:
            records = to_dict_fn("records")
            if isinstance(records, list):
                return [item for item in records if isinstance(item, dict)]
        except Exception:
            return []
    return []


def _load_akshare_module() -> Any:
    try:
        return importlib.import_module(AKSHARE_MODULE_NAME)
    except ModuleNotFoundError:
        return None


def _normalize_market(value: Any) -> str:
    text = str(value or "").upper()
    if text in ("SH", "SSE", "1"):
        return "SH"
    if text in ("SZ", "SZSE", "0", "2"):
        return "SZ"
    return text or "A"


def _normalize_trade_date_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = (
        text.replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .replace("/", "-")
        .replace("T", " ")
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(normalized, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    matched = re.search(r"(20\d{2}-\d{1,2}-\d{1,2})", normalized)
    if matched:
        try:
            dt = datetime.strptime(matched.group(1), "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return ""
    return ""


def _normalize_security_record(record: dict) -> dict:
    normalized = {}
    for field, aliases in AKSHARE_SECURITY_FIELD_ALIASES.items():
        normalized[field] = _get_value_by_alias(record, aliases, "")
    normalized["symbol"] = str(normalized.get("symbol") or "").strip()
    normalized["name"] = str(normalized.get("name") or "").strip()
    normalized["market"] = _normalize_market(normalized.get("market"))
    normalized["trade_date"] = _normalize_trade_date_text(normalized.get("trade_date"))
    for numeric_field in (
        "last_price",
        "change_percent",
        "turnover_rate",
        "volume_ratio",
        "pe_ttm",
        "pb",
        "amount",
        "volume",
    ):
        normalized[numeric_field] = _safe_number(normalized.get(numeric_field))
    return normalized


def _filter_security_records(records: list, keyword: str, limit: int) -> list:
    if not records:
        return []
    normalized_keyword = str(keyword or "").strip().lower()
    result = []
    for record in records:
        normalized = _normalize_security_record(record)
        if not normalized.get("symbol"):
            continue
        if normalized_keyword:
            code_hit = normalized_keyword in str(normalized.get("symbol", "")).lower()
            name_hit = normalized_keyword in str(normalized.get("name", "")).lower()
            if not code_hit and not name_hit:
                continue
        result.append(normalized)
        if len(result) >= limit:
            break
    return result


def query_akshare_securities(keyword: str = "", limit: int = 20) -> dict:
    normalized_limit = 20 if limit is None else int(limit)
    if normalized_limit <= 0:
        return _build_standard_error(
            code=STANDARD_ERROR_CODE_INVALID_ARGUMENT,
            message="limit 必须为正整数",
            details={"limit": limit},
        )
    ak = _load_akshare_module()
    if ak is None:
        return _build_standard_error(
            code=STANDARD_ERROR_CODE_AKSHARE_NOT_INSTALLED,
            message="未安装 AKShare，请先执行 `pip install akshare`",
            retryable=False,
        )
    try:
        raw = ak.stock_zh_a_spot_em()
        records = _safe_records(raw)
        if not records:
            return _build_standard_error(
                code=STANDARD_ERROR_CODE_DATA_EMPTY,
                message="AKShare 未返回证券数据",
                retryable=True,
            )
        matched = _filter_security_records(records, keyword=keyword, limit=normalized_limit)
        if not matched:
            return _build_standard_error(
                code=STANDARD_ERROR_CODE_DATA_EMPTY,
                message="未查询到匹配证券",
                retryable=False,
                details={"keyword": keyword},
            )
        return _build_standard_result(
            data={"items": matched, "total": len(matched)},
            meta={"provider": AKSHARE_MODULE_NAME, "endpoint": "stock_zh_a_spot_em"},
        )
    except AttributeError as error:
        return _build_standard_error(
            code=STANDARD_ERROR_CODE_DATA_SCHEMA_ERROR,
            message="AKShare 接口不存在或版本不兼容",
            retryable=False,
            details={"error": str(error)},
            meta={"provider": AKSHARE_MODULE_NAME},
        )
    except Exception as error:
        return _build_standard_error(
            code=STANDARD_ERROR_CODE_AKSHARE_API_ERROR,
            message="AKShare 证券查询失败",
            retryable=True,
            details={"error": str(error), "keyword": keyword},
            meta={"provider": AKSHARE_MODULE_NAME},
        )


def query_akshare_quote(symbol: str) -> dict:
    normalized_symbol = str(symbol or "").strip()
    if not validate_stock_code(normalized_symbol):
        return _build_standard_error(
            code=STANDARD_ERROR_CODE_INVALID_ARGUMENT,
            message="symbol 必须是合法 A 股 6 位代码",
            details={"symbol": symbol},
        )
    result = query_akshare_securities(keyword=normalized_symbol, limit=1)
    if not result.get("success"):
        return result
    quote = _as_list(_dig_path(result, [["data", "items"]], default=[]))
    exact = [item for item in quote if str(item.get("symbol", "")) == normalized_symbol]
    if not exact:
        return _build_standard_error(
            code=STANDARD_ERROR_CODE_DATA_EMPTY,
            message="未查询到该证券实时行情",
            retryable=False,
            details={"symbol": normalized_symbol},
            meta=result.get("meta"),
        )
    quote = exact[0]
    standardized = {
        "symbol": quote.get("symbol", normalized_symbol),
        "name": quote.get("name", ""),
        "price": quote.get("last_price", ""),
        "trade_date": quote.get("trade_date", ""),
    }
    return _build_standard_result(
        data={"quote": quote, "standardized": standardized},
        meta=result.get("meta"),
    )


def _normalize_query_field_name(field: Any) -> str:
    return str(field or "").strip().lower()


def _extract_key_fields_from_akshare_quote(quote: dict, requested_fields: list) -> dict:
    if not isinstance(quote, dict):
        return {}
    key_fields = {}
    for raw_field in requested_fields:
        field_name = str(raw_field or "").strip()
        if not field_name:
            continue
        mapped_field = AKSHARE_QUERY_FIELD_MAP.get(_normalize_query_field_name(field_name), "")
        if not mapped_field:
            continue
        value = quote.get(mapped_field)
        if value in (None, ""):
            continue
        key_fields[field_name] = value
    return key_fields


def _pick_trade_date_from_source_timestamp(timestamp_text: str) -> str:
    raw = str(timestamp_text or "").strip()
    if not raw:
        return ""
    matched = re.search(r"(20\d{2}-\d{1,2}-\d{1,2})", raw)
    if not matched:
        return ""
    return _normalize_trade_date_text(matched.group(1))


def _build_standardized_key_fields(
    request_payload: dict,
    selected_key_fields: dict,
    akshare_quote: dict,
    source_timestamp: str,
) -> dict:
    request_data = _as_dict(request_payload)
    quote = _as_dict(akshare_quote)
    price = (
        selected_key_fields.get("price")
        if "price" in selected_key_fields
        else selected_key_fields.get("latest_price", "")
    )
    trade_date = (
        quote.get("trade_date")
        or _pick_trade_date_from_source_timestamp(source_timestamp)
        or datetime.now().strftime("%Y-%m-%d")
    )
    return {
        "symbol": str(
            quote.get("symbol")
            or request_data.get("stock_code")
            or request_data.get("symbol")
            or ""
        ),
        "name": str(quote.get("name") or request_data.get("stock_name") or ""),
        "price": price,
        "trade_date": trade_date,
    }


def _mask_secret(value: str, keep_start: int = 3, keep_end: int = 2) -> str:
    raw = str(value or "")
    if len(raw) <= keep_start + keep_end:
        return "*" * len(raw)
    return f"{raw[:keep_start]}{'*' * (len(raw) - keep_start - keep_end)}{raw[-keep_end:]}"


def _desensitize_payload(payload: dict) -> dict:
    sensitive_keys = ("apikey", "api_key", "token", "authorization", "password", "secret", "sign")
    safe_payload = {}
    for key, value in (payload or {}).items():
        key_text = str(key).lower()
        if any(s in key_text for s in sensitive_keys):
            safe_payload[key] = _mask_secret(value)
        else:
            safe_payload[key] = value
    return safe_payload


def get_eastmoney_apikey(required: bool = True) -> str:
    apikey = (os.getenv(EASTMONEY_APIKEY_ENV) or os.getenv("EASTMONEY_API_KEY") or os.getenv("EM_API_KEY") or "").strip()
    if not apikey:
        apikey = _load_eastmoney_apikey_from_env_files()
    if required and not apikey:
        raise EastmoneyApiKeyMissingError(
            f"环境变量 {EASTMONEY_APIKEY_ENV} 未配置，无法执行东财 POST 请求"
        )
    return apikey


def _load_eastmoney_apikey_from_env_files() -> str:
    for file_name in _ENV_FILE_CANDIDATES:
        key = _extract_key_from_env_file(_SKILL_ROOT / file_name, EASTMONEY_APIKEY_ENV)
        if key:
            return key
    return ""


def _extract_key_from_env_file(file_path: Path, key_name: str) -> str:
    if not file_path.exists():
        return ""
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for raw_line in lines:
        line = (raw_line or "").strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        left, right = line.split("=", 1)
        current_key = left.strip()
        if current_key != key_name:
            continue
        value = right.strip()
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        return value.strip()
    return ""


def _load_daily_counter() -> dict:
    if not _EASTMONEY_COUNTER_FILE.exists():
        return {"date": datetime.now().strftime("%Y-%m-%d"), "count": 0}
    try:
        with _EASTMONEY_COUNTER_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"date": datetime.now().strftime("%Y-%m-%d"), "count": 0}
    return {
        "date": str(data.get("date") or datetime.now().strftime("%Y-%m-%d")),
        "count": int(data.get("count") or 0),
    }


def _save_daily_counter(counter: dict) -> None:
    _EASTMONEY_COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _EASTMONEY_COUNTER_FILE.open("w", encoding="utf-8") as f:
        json.dump(counter, f, ensure_ascii=False)


def consume_eastmoney_daily_quota() -> dict:
    """
    消费一次东财接口日配额（50次/日）
    """
    with _EASTMONEY_COUNTER_LOCK:
        today = datetime.now().strftime("%Y-%m-%d")
        counter = _load_daily_counter()
        if counter["date"] != today:
            counter = {"date": today, "count": 0}
        if counter["count"] >= EASTMONEY_DAILY_LIMIT:
            raise EastmoneyDailyLimitError(
                f"东财接口日调用已达上限 {EASTMONEY_DAILY_LIMIT} 次，今日不再继续请求"
            )
        counter["count"] += 1
        _save_daily_counter(counter)
    return {
        "date": counter["date"],
        "count": counter["count"],
        "remaining": max(EASTMONEY_DAILY_LIMIT - counter["count"], 0),
    }


def get_eastmoney_daily_usage() -> dict:
    """
    查看今日已用/剩余配额（不会消耗配额）
    """
    with _EASTMONEY_COUNTER_LOCK:
        today = datetime.now().strftime("%Y-%m-%d")
        counter = _load_daily_counter()
        if counter["date"] != today:
            counter = {"date": today, "count": 0}
        return {
            "date": counter["date"],
            "count": counter["count"],
            "remaining": max(EASTMONEY_DAILY_LIMIT - counter["count"], 0),
            "limit": EASTMONEY_DAILY_LIMIT,
        }


def post_json(url: str, payload: dict, headers: dict = None, timeout: int = 10) -> dict:
    """
    POST 封装1：通用 JSON POST
    """
    merged_headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    }
    if headers:
        merged_headers.update(headers)
    request_data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    req = Request(url=url, data=request_data, headers=merged_headers, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            body = resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        body = (e.read() or b"").decode("utf-8", errors="replace")
        raise EastmoneyHttpError(
            f"POST失败 status={e.code} url={url} body={_mask_secret(body, 0, 0)[:180]}"
        ) from e
    except (URLError, TimeoutError, OSError) as e:
        raise EastmoneyHttpError(f"POST失败 url={url} reason={str(e)}") from e

    if status >= 400:
        raise EastmoneyHttpError(
            f"POST失败 status={status} url={url} body={_mask_secret(body, 0, 0)[:180]}"
        )
    if not body.strip():
        return {}
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as e:
        raise EastmoneyDecodeError(
            f"POST响应不是合法JSON url={url} body_preview={body[:180]}"
        ) from e
    return parsed if isinstance(parsed, dict) else {"data": parsed}


def post_json_with_retry(
    url: str,
    payload: dict,
    headers: dict = None,
    timeout: int = 10,
    retries: int = 2,
) -> dict:
    """
    POST 封装2：带重试的 JSON POST（失败抛出最后一次异常）
    """
    last_error = None
    for attempt in range(1, retries + 2):
        try:
            return post_json(url=url, payload=payload, headers=headers, timeout=timeout)
        except EastmoneyPostError as e:
            last_error = e
            LOGGER.warning(
                "POST重试 %s/%s url=%s payload=%s err=%s",
                attempt,
                retries + 1,
                url,
                _desensitize_payload(payload),
                str(e),
            )
    raise last_error


def post_eastmoney(
    endpoint: str,
    payload: dict,
    timeout: int = 10,
    retries: int = 1,
    use_daily_limit: bool = True,
) -> dict:
    """
    POST 封装3：东财专用封装（EASTMONEY_APIKEY + 50次/日 + 脱敏日志 + 异常处理）
    """
    apikey = get_eastmoney_apikey(required=True)
    target_url = _build_eastmoney_url(endpoint)

    quota = None
    if use_daily_limit:
        quota = consume_eastmoney_daily_quota()
    LOGGER.info(
        "调用东财POST url=%s apikey=%s quota=%s payload=%s",
        target_url,
        _mask_secret(apikey),
        quota or "skip",
        _desensitize_payload(payload),
    )
    headers = {
        "apikey": apikey,
        "X-Api-Key": apikey,
    }
    return post_json_with_retry(
        url=target_url,
        payload=payload,
        headers=headers,
        timeout=timeout,
        retries=retries,
    )


def _build_eastmoney_url(endpoint: str) -> str:
    target = (endpoint or "").strip()
    if not target:
        return EASTMONEY_BASE_URL.rstrip("/")
    if target.startswith(("http://", "https://")):
        return target
    base = EASTMONEY_BASE_URL.rstrip("/") + "/"
    return urljoin(base, target.lstrip("/"))


def _dig_path(payload: Any, paths: list, default: Any = None) -> Any:
    for path in paths:
        current = payload
        ok = True
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current.get(key)
            else:
                ok = False
                break
        if ok:
            return current
    return default


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _as_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    return {}


def _pick_first(data: dict, keys: list, default: Any = None) -> Any:
    if not isinstance(data, dict):
        return default
    for key in keys:
        if key in data and data.get(key) not in (None, ""):
            return data.get(key)
    return default


def _extract_common_meta(resp: dict) -> dict:
    code = _pick_first(resp, ["code", "errCode", "status", "errno"], "")
    message = _pick_first(resp, ["msg", "message", "errMsg", "error"], "")
    success = str(code) in ("", "0", "200", "10000") and "失败" not in str(message)
    return {"code": code, "message": str(message), "success": bool(success)}


def _detect_large_range_blocked(resp: dict) -> bool:
    raw = json.dumps(resp or {}, ensure_ascii=False)
    flags = ["范围过大", "too large", "exceed", "超限", "保护", "limit"]
    return any(flag.lower() in raw.lower() for flag in flags)


def _extract_source_timestamp(raw: dict, fallback_text: str = "") -> str:
    timestamp = (
        _pick_first(raw, ["publishTime", "pubTime", "time", "datetime", "date"], "")
        or extract_timestamp_text(fallback_text)
    )
    return normalize_timestamp_text(str(timestamp))


def _normalize_security_item(item: Any) -> dict:
    if isinstance(item, str):
        return {"code": item, "name": "", "market": ""}
    data = _as_dict(item)
    return {
        "code": str(_pick_first(data, ["code", "secuCode", "symbol", "securityCode"], "") or ""),
        "name": str(_pick_first(data, ["name", "secuName", "securityName"], "") or ""),
        "market": str(_pick_first(data, ["market", "marketCode", "mkt"], "") or ""),
    }


def eastmoney_news_search(
    question: str,
    stock_code: str = "",
    stock_name: str = "",
    time_range: str = "",
    page: int = 1,
    page_size: int = 10,
    timeout: int = 10,
    retries: int = 1,
) -> dict:
    payload = {
        "question": question,
        "query": question,
        "keyword": question,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "time_range": time_range,
        "page": max(int(page or 1), 1),
        "page_size": max(min(int(page_size or 10), 50), 1),
    }
    resp = post_eastmoney(
        endpoint=EASTMONEY_ENDPOINT_NEWS_SEARCH,
        payload=payload,
        timeout=timeout,
        retries=retries,
    )
    return parse_eastmoney_news_search_response(resp, request_payload=payload)


def parse_eastmoney_news_search_response(resp: dict, request_payload: dict = None) -> dict:
    data = resp or {}
    meta = _extract_common_meta(data)
    rows = _as_list(
        _dig_path(
            data,
            [
                ["data", "list"],
                ["result", "list"],
                ["result", "result", "list"],
                ["data", "result", "list"],
                ["list"],
            ],
            default=[],
        )
    )
    items = []
    for row in rows:
        current = _as_dict(row)
        secu_list = _as_list(current.get("secuList") or current.get("securityList") or [])
        title = str(_pick_first(current, ["title", "name"], "") or "")
        trunk = str(_pick_first(current, ["trunk", "summary", "content", "abstract", "snippet"], "") or "")
        source = str(_pick_first(current, ["source", "src", "media"], "") or "")
        link = str(_pick_first(current, ["url", "link", "weburl"], "") or "")
        source_timestamp = _extract_source_timestamp(current, fallback_text=f"{title} {trunk}")
        items.append(
            {
                "title": title,
                "trunk": trunk,
                "source": source,
                "publish_time": source_timestamp,
                "link": link,
                "secuList": [_normalize_security_item(item) for item in secu_list],
                "raw": current,
            }
        )
    empty_result = len(items) == 0
    return {
        "endpoint": "news-search",
        "meta": meta,
        "request_payload": _desensitize_payload(request_payload or {}),
        "total": len(items),
        "items": items,
        "empty_result": empty_result,
        "empty_result_tip": EASTMONEY_EMPTY_RESULT_TIP if empty_result else "",
    }


def eastmoney_query(
    question: str,
    stock_code: str = "",
    stock_name: str = "",
    fields: list = None,
    granularity: str = "day",
    time_range: str = "",
    timeout: int = 10,
    retries: int = 1,
) -> dict:
    fields = fields or []
    payload = {
        "question": question,
        "query": question,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "fields": fields,
        "granularity": granularity,
        "time_range": time_range,
    }
    resp = post_eastmoney(
        endpoint=EASTMONEY_ENDPOINT_QUERY,
        payload=payload,
        timeout=timeout,
        retries=retries,
    )
    akshare_result = {}
    if validate_stock_code(stock_code):
        akshare_result = query_akshare_quote(stock_code)
    return parse_eastmoney_query_response(resp, request_payload=payload, akshare_result=akshare_result)


def parse_eastmoney_query_response(resp: dict, request_payload: dict = None, akshare_result: dict = None) -> dict:
    data = resp or {}
    meta = _extract_common_meta(data)
    data_root = _dig_path(data, [["data"], ["result", "data"], ["result", "result", "data"]], default={})
    records = _as_list(
        _dig_path(
            data,
            [
                ["data", "list"],
                ["result", "list"],
                ["result", "result", "list"],
                ["list"],
            ],
            default=[],
        )
    )
    requested_fields = _as_list((request_payload or {}).get("fields"))
    base_sample = _as_dict(records[0]) if records and isinstance(records[0], dict) else _as_dict(data_root)
    eastmoney_key_fields = {field: base_sample.get(field) for field in requested_fields if field in base_sample}
    selected_key_fields = dict(eastmoney_key_fields)
    key_fields_provider = "eastmoney_query"
    key_fields_priority = 2
    akshare_quote = _as_dict(_dig_path(akshare_result or {}, [["data", "quote"]], default={}))
    if (akshare_result or {}).get("success") and akshare_quote:
        selected_key_fields = _extract_key_fields_from_akshare_quote(akshare_quote, requested_fields)
        key_fields_provider = "akshare"
        key_fields_priority = 1
    missing_fields = [field for field in requested_fields if field not in selected_key_fields]
    blocked_by_guardrail = _detect_large_range_blocked(data)
    source_timestamp = _extract_source_timestamp(base_sample, fallback_text=json.dumps(base_sample, ensure_ascii=False))
    standardized_key_fields = _build_standardized_key_fields(
        request_payload=request_payload or {},
        selected_key_fields=selected_key_fields,
        akshare_quote=akshare_quote,
        source_timestamp=source_timestamp,
    )
    data_has_payload = isinstance(data_root, dict) and any(value not in (None, "", [], {}) for value in data_root.values())
    empty_result = not bool(records or data_has_payload)
    return {
        "endpoint": "query",
        "meta": meta,
        "request_payload": _desensitize_payload(request_payload or {}),
        "data": data_root if data_root else {"list": records} if records else {},
        "records": records,
        "key_fields": selected_key_fields,
        "missing_fields": missing_fields,
        "key_fields_provider": key_fields_provider,
        "key_fields_priority": key_fields_priority,
        "standardized_key_fields": standardized_key_fields,
        "key_fields_source_priority": list(QUERY_KEY_FIELD_SOURCE_PRIORITY),
        "model_completion_forbidden": True,
        "supplemental_news_only": True,
        "fallback_key_fields": eastmoney_key_fields if key_fields_provider == "akshare" else {},
        "source_timestamp": source_timestamp,
        "blocked_by_guardrail": blocked_by_guardrail,
        "guardrail_tip": EASTMONEY_BLOCKED_RESULT_TIP if blocked_by_guardrail else "",
        "empty_result": empty_result,
    }


def eastmoney_stock_screen(
    conditions: dict,
    sort_by: str = "",
    sort_order: str = "desc",
    limit: int = 50,
    timeout: int = 10,
    retries: int = 1,
) -> dict:
    payload = {
        "conditions": _as_dict(conditions),
        "sort_by": sort_by,
        "sort_order": sort_order,
        "limit": max(min(int(limit or 50), 50), 1),
    }
    resp = post_eastmoney(
        endpoint=EASTMONEY_ENDPOINT_STOCK_SCREEN,
        payload=payload,
        timeout=timeout,
        retries=retries,
    )
    return parse_eastmoney_stock_screen_response(resp, request_payload=payload)


def parse_eastmoney_stock_screen_response(resp: dict, request_payload: dict = None) -> dict:
    data = resp or {}
    meta = _extract_common_meta(data)
    columns = _as_list(
        _dig_path(
            data,
            [["data", "columns"], ["result", "columns"], ["result", "result", "columns"], ["columns"]],
            default=[],
        )
    )
    rows = _as_list(
        _dig_path(
            data,
            [["data", "rows"], ["data", "list"], ["result", "rows"], ["result", "list"], ["list"]],
            default=[],
        )
    )
    normalized_columns = []
    column_keys = []
    for item in columns:
        if isinstance(item, str):
            field = item
            label = EASTMONEY_STOCK_SCREEN_COLUMN_MAP.get(field.lower(), field)
        else:
            column_def = _as_dict(item)
            field = str(_pick_first(column_def, ["field", "key", "name", "code"], "") or "")
            default_label = EASTMONEY_STOCK_SCREEN_COLUMN_MAP.get(field.lower(), field)
            label = str(_pick_first(column_def, ["label", "title", "displayName"], default_label) or default_label)
        if field:
            column_keys.append(field)
            normalized_columns.append({"field": field, "label": label})

    normalized_rows = []
    for row in rows:
        if isinstance(row, dict):
            row_dict = dict(row)
        elif isinstance(row, list) and column_keys:
            row_dict = {column_keys[idx]: row[idx] for idx in range(min(len(column_keys), len(row)))}
        else:
            row_dict = {"value": row}
        stock_code = str(_pick_first(row_dict, ["stock_code", "code", "secu_code", "symbol", "security_code"], "") or "")
        stock_name = str(_pick_first(row_dict, ["stock_name", "name", "secu_name", "security_name"], "") or "")
        sort_value = _pick_first(row_dict, ["sort_value", "score", "rank_value"], "")
        matched_conditions = _as_list(_pick_first(row_dict, ["matched_conditions", "hit_conditions", "rules"], []))
        normalized_rows.append(
            {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "matched_conditions": matched_conditions,
                "sort_value": sort_value,
                "raw": row_dict,
            }
        )

    empty_result = len(normalized_rows) == 0
    total = _pick_first(
        _as_dict(_dig_path(data, [["data"], ["result"], ["result", "result"]], default={})),
        ["total", "count", "total_count"],
        len(normalized_rows),
    )
    return {
        "endpoint": "stock-screen",
        "meta": meta,
        "request_payload": _desensitize_payload(request_payload or {}),
        "columns": normalized_columns,
        "rows": normalized_rows,
        "total": int(total or 0),
        "empty_result": empty_result,
        "empty_result_tip": EASTMONEY_EMPTY_RESULT_TIP if empty_result else "",
        "export": {
            "columns": normalized_columns,
            "rows": [row["raw"] for row in normalized_rows],
            "total": int(total or 0),
        },
    }


def _compact_name_text(text: str) -> str:
    return re.sub(r"[\s·\-\(\)（）【】\[\]A股港股美股]+", "", (text or "").strip())


def _strip_company_suffix(name: str) -> str:
    normalized = name
    for suffix in ("股份有限公司", "有限责任公司", "有限公司"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break
    return normalized


def normalize_stock_name(name: str) -> str:
    """
    统一股票名称表达，支持常见噪声清洗与别名归一
    """
    raw = (name or "").strip()
    if not raw:
        return ""
    normalized = _compact_name_text(raw)
    normalized = _strip_company_suffix(normalized)
    normalized = normalized.replace("*ST", "ST").replace("ＳＴ", "ST")
    match_candidates = {normalized}
    if normalized.upper().startswith("ST"):
        match_candidates.add(normalized[2:])
    for canonical, aliases in STOCK_NAME_ALIAS_MAP.items():
        candidates = [canonical, *aliases]
        normalized_candidates = {_strip_company_suffix(_compact_name_text(item)) for item in candidates}
        if any(candidate in normalized_candidates for candidate in match_candidates):
            return canonical
    return normalized


def is_stock_name_alias(left: str, right: str) -> bool:
    """
    判断两个股票名称是否属于同一主体（含别名）
    """
    normalized_left = normalize_stock_name(left)
    normalized_right = normalize_stock_name(right)
    if not normalized_left or not normalized_right:
        return False
    return normalized_left == normalized_right

def validate_stock_code(code: str) -> bool:
    """
    验证股票代码格式

    Args:
        code: 股票代码

    Returns:
        是否有效
    """
    # A股代码: 6位数字，以6/0/3开头
    pattern = r'^[036]\d{5}$'
    return bool(re.match(pattern, code))


def extract_stock_code(user_input: str) -> str:
    """
    从用户输入中提取股票代码

    Args:
        user_input: 用户输入，如 "600684" 或 "珠江股份 600684"

    Returns:
        股票代码，如 "600684"
    """
    # 尝试直接匹配6位数字
    match = re.search(r'\b(\d{6})\b', user_input)
    if match:
        code = match.group(1)
        if validate_stock_code(code):
            return code

    return ""


def get_search_queries(stock_code: str, stock_name: str = "") -> list:
    """
    生成搜索查询语句

    Args:
        stock_code: 股票代码
        stock_name: 股票名称（可选）

    Returns:
        搜索关键词列表
    """
    queries = []
    year = datetime.now().year

    if stock_name:
        queries.append(f"{stock_name} {stock_code} 股票 今日行情 近3日")
        queries.append(f"{stock_name} {stock_code} 主力资金流向 近5日")
        queries.append(f"{stock_name} {stock_code} 营业收入 同比 环比 {year}")
        queries.append(f"{stock_name} {stock_code} 业绩预告 最新")
    else:
        queries.append(f"{stock_code} 股票 今日行情 近3日")
        queries.append(f"{stock_code} 主力资金流向 近5日")
        queries.append(f"{stock_code} 营业收入 同比 环比 {year}")
        queries.append(f"{stock_code} 业绩预告 最新")

    return queries


def get_realtime_source_pool() -> dict:
    """
    定义核心字段的多源采集池与分类

    Returns:
        多源配置字典
    """
    return {
        "core_fields": ["price", "change", "turnover", "main", "retail"],
        "source_priority": list(QUERY_KEY_FIELD_SOURCE_PRIORITY),
        # 修复：从3降至2，实际可达到;
        # 要求来源类别数小于3同样会导致对正常数据的误报
        "required_categories": 2,
        # 修复：从90分钟改为179分钟（约3小时）
        # 原90分钟太严格：A股正常盘中数据跨度通常在2.5小时内
        # 180分钟边界值（使 09:30~12:30 = 180min > 179min 生效检测）
        # 能检出真实的跨早/尾盘数据质量问题，同时不误报正常数据
        "timestamp_conflict_threshold_minutes": 179,
        "category_hints": {
            "交易所/监管": [
                "sse.com.cn", "szse.cn", "cninfo.com.cn", "csrc.gov.cn",
                "neeq.com.cn", "sse.org.cn",
            ],
            "行情终端": [
                "eastmoney.com", "10jqka.com.cn", "cls.cn", "stcn.com",
                "xueqiu.com", "sina.com.cn", "finance.sina", "cfi.cn",
                "stockstar.com", "jrj.com.cn", "hexun.com",
                "gtimg.com", "ifeng.com", "163.com",
            ],
            "财经媒体": [
                "caixin.com", "yicai.com", "cnstock.com", "stcn.com",
                "cs.com.cn", "21jingji.com", "bjnews.com.cn",
                "thepaper.cn", "nbd.com.cn", "chinastock.com.cn",
                "chinabond.com.cn", "bloomberg.cn",
            ],
            "券商研报": [
                "cmschina.com", "htsc.com.cn", "citics.com",
                "guosen.com.cn", "htsec.com", "swsresearch.com",
                "gtja.com", "csc.com.cn",
            ],
        },
    }


def infer_source_category(link: str, title: str = "") -> str:
    """
    根据链接域名和标题推断来源类别
    """
    normalized = (link or "").lower()
    host = ""
    if normalized:
        try:
            host = urlparse(normalized).netloc.lower()
        except Exception:
            host = ""
    text = f"{host} {(title or '').lower()}"
    source_pool = get_realtime_source_pool()
    for category, hints in source_pool.get("category_hints", {}).items():
        if any(hint in text for hint in hints):
            return category
    if "交易所" in title or "公告" in title:
        return "交易所/监管"
    if "研报" in title:
        return "券商研报"
    return "其他来源"


def extract_timestamp_text(text: str, default: str = "") -> str:
    """
    从文本中抽取时间戳字符串，优先返回分钟级格式
    """
    if not text:
        return default
    patterns = [
        r"(20\d{2}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2})",
        r"(20\d{2}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2})",
        r"(20\d{2}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2})",
        r"(20\d{2}-\d{1,2}-\d{1,2})",
        r"(20\d{2}/\d{1,2}/\d{1,2})",
        r"(20\d{2}年\d{1,2}月\d{1,2}日)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return default


def normalize_timestamp_text(timestamp_text: str) -> str:
    """
    将常见日期时间文本规范化为 YYYY-MM-DD HH:MM
    """
    raw = (timestamp_text or "").strip()
    if not raw:
        return ""
    compact = (
        raw.replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .replace("/", "-")
        .replace("T", " ")
    )
    compact = re.sub(r"\s+", " ", compact).strip()
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(compact, fmt)
            if fmt == "%Y-%m-%d":
                return dt.strftime("%Y-%m-%d 00:00")
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
    return ""


def get_shortline_indicator_recommendations() -> dict:
    indicator_items = [
        {
            "priority": "必须",
            "indicator": "VWAP偏离",
            "data_source": "分时价格、成交额、成交量",
            "trigger_rule": "绝对偏离>=2.0%触发强提醒",
            "collect_entry": "stock_utils.get_search_queries",
            "calc_entry": "generate_report._generate_minimal_shortline_recommendation",
            "route_entry": "team_router.build_shortline_supervisor_rules",
            "output_entry": "generate_report._build_shortline_signal_lines",
            "report_position": "综合结论/短线信号确认",
            "risk": "单日脉冲行情会放大偏离噪声",
        },
        {
            "priority": "必须",
            "indicator": "ATR止损",
            "data_source": "近14日高低收",
            "trigger_rule": "建议止损=当前价-1.5*ATR",
            "collect_entry": "stock_utils.get_search_queries",
            "calc_entry": "generate_report._generate_minimal_shortline_recommendation",
            "route_entry": "team_router.build_shortline_supervisor_rules",
            "output_entry": "generate_report._build_shortline_signal_lines",
            "report_position": "操作建议/止损价",
            "risk": "极端波动日可能导致止损过宽",
        },
        {
            "priority": "必须",
            "indicator": "量比",
            "data_source": "即时成交量、5日均量",
            "trigger_rule": "量比>=1.8且价格上破压力位视作确认",
            "collect_entry": "stock_utils.get_search_queries",
            "calc_entry": "generate_report._generate_minimal_shortline_recommendation",
            "route_entry": "team_router.build_shortline_supervisor_rules",
            "output_entry": "generate_report._build_shortline_signal_lines",
            "report_position": "技术分析派/触发确认",
            "risk": "消息驱动放量可能造成假突破",
        },
        {
            "priority": "建议",
            "indicator": "5日资金斜率",
            "data_source": "近5日主力净额",
            "trigger_rule": "斜率由正转负触发降级",
            "collect_entry": "stock_utils.get_search_queries",
            "calc_entry": "generate_report._generate_minimal_shortline_recommendation",
            "route_entry": "team_router.build_shortline_supervisor_rules",
            "output_entry": "generate_report._build_reversal_warning",
            "report_position": "资金流向反转预警",
            "risk": "节假日前后资金口径变化导致噪声",
        },
        {
            "priority": "建议",
            "indicator": "突破回踩确认",
            "data_source": "支撑位、压力位、分时回落幅度",
            "trigger_rule": "突破后回踩不破且放量恢复",
            "collect_entry": "stock_utils.get_search_queries",
            "calc_entry": "generate_report._generate_minimal_shortline_recommendation",
            "route_entry": "team_router.build_shortline_supervisor_rules",
            "output_entry": "generate_report._build_shortline_signal_lines",
            "report_position": "专家讨论纪要",
            "risk": "无分钟级数据时易误判",
        },
        {
            "priority": "可选",
            "indicator": "异动公告计数",
            "data_source": "近3日公告与监管提示",
            "trigger_rule": "3日累计异动公告>=1标注监管风险",
            "collect_entry": "stock_utils.get_search_queries",
            "calc_entry": "generate_report._generate_minimal_shortline_recommendation",
            "route_entry": "team_router.build_shortline_supervisor_rules",
            "output_entry": "generate_report._build_shortline_signal_lines",
            "report_position": "风险提示",
            "risk": "资讯抓取延迟影响实时性",
        },
    ]
    priority_order = ["必须", "建议", "可选"]
    grouped = {}
    for level in priority_order:
        grouped[level] = [item for item in indicator_items if item["priority"] == level]
    return {
        "layers": grouped,
        "code_entry_mapping": indicator_items,
        "minimum_rollout_order": [
            {"step": "先路由", "done_standard": "team模式可返回短线任务字段"},
            {"step": "再指标", "done_standard": "最小建议函数产出分层与映射"},
            {"step": "后模板", "done_standard": "报告出现短线信号与降级原因"},
        ],
        "compatibility_notes": [
            "脚本保持标准库依赖，避免跨机缺包",
            "路径使用相对路径，避免目录差异",
            "缺失关键指标时结论不允许强可做",
        ],
    }


if __name__ == "__main__":
    # 测试
    print("=== 股票代码验证测试 ===")
    print(f"600684: {validate_stock_code('600684')}")
    print(f"000001: {validate_stock_code('000001')}")
    print(f"300750: {validate_stock_code('300750')}")
    print(f"123456: {validate_stock_code('123456')}")

    print("\n=== 提取股票代码 ===")
    print(f"'600684': {extract_stock_code('600684')}")
    print(f"'珠江股份600684': {extract_stock_code('珠江股份600684')}")
    print(f"'分析一下招商银行': {extract_stock_code('分析一下招商银行')}")

    print("\n=== 搜索查询 ===")
    for q in get_search_queries("600684", "珠江股份"):
        print(f"- {q}")
