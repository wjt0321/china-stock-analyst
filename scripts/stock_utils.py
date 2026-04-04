# A股分析辅助脚本
# 关键字段主来源为 Web Search，东财用于结构化复核

# 股票代码正则验证
import json
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

STANDARD_ERROR_CODE_INVALID_ARGUMENT = "INVALID_ARGUMENT"
STANDARD_ERROR_CODE_DATA_EMPTY = "DATA_EMPTY"
STANDARD_ERROR_CODE_DATA_SCHEMA_ERROR = "DATA_SCHEMA_ERROR"
STANDARD_ERROR_CODE_INTERNAL_ERROR = "INTERNAL_ERROR"
QUERY_KEY_FIELD_SOURCE_PRIORITY = [
    {"provider": "web_search", "priority": 1, "scope": "primary_market_snapshot"},
    {"provider": "eastmoney_query", "priority": 2, "scope": "structured_verification"},
]
QUERY_FIELD_MAP = {
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
DATA_EVIDENCE_REQUIRED_FIELDS = ("price", "change_percent", "turnover_rate", "main_net_inflow")


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


class EastmoneyQuotaPersistError(EastmoneyPostError):
    """日配额持久化异常"""


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


def _normalize_query_field_name(field: Any) -> str:
    return str(field or "").strip().lower()


def _extract_key_fields_from_query_row(row: dict, requested_fields: list) -> dict:
    if not isinstance(row, dict):
        return {}
    key_fields = {}
    for raw_field in requested_fields:
        field_name = str(raw_field or "").strip()
        if not field_name:
            continue
        mapped_field = QUERY_FIELD_MAP.get(_normalize_query_field_name(field_name), "")
        normalized_field = _normalize_query_field_name(field_name)
        if not mapped_field:
            mapped_field = normalized_field
        value = row.get(mapped_field)
        if value in (None, "") and normalized_field != mapped_field:
            value = row.get(normalized_field)
        if value in (None, ""):
            value = row.get(field_name)
        if value in (None, ""):
            continue
        key_fields[field_name] = value
    return key_fields


def _build_data_evidences(query_row: dict, requested_fields: list, source_timestamp: str) -> list:
    row = _as_dict(query_row)
    evidences = []
    for raw_field in requested_fields:
        field_name = str(raw_field or "").strip()
        if not field_name:
            continue
        normalized_field = _normalize_query_field_name(field_name)
        mapped_field = QUERY_FIELD_MAP.get(normalized_field, normalized_field)
        candidates = [mapped_field]
        if normalized_field not in candidates:
            candidates.append(normalized_field)
        if field_name not in candidates:
            candidates.append(field_name)
        resolved_value = None
        resolved_key = ""
        for candidate in candidates:
            value = row.get(candidate)
            if value in (None, ""):
                continue
            resolved_value = value
            resolved_key = str(candidate)
            break
        if resolved_value in (None, ""):
            continue
        evidences.append(
            {
                "field": field_name,
                "normalized_field": normalized_field,
                "value": resolved_value,
                "source_field": resolved_key or mapped_field,
                "source_type": "eastmoney_query",
                "source_url": "eastmoney://query",
                "source_timestamp": source_timestamp or "",
                "verified_by_eastmoney": True,
                "confidence": "high" if source_timestamp else "medium",
            }
        )
    return evidences


def _build_field_conflict_summary(query_row: dict, requested_fields: list) -> dict:
    row = _as_dict(query_row)
    conflicts = []
    for raw_field in requested_fields:
        field_name = str(raw_field or "").strip()
        if not field_name:
            continue
        normalized_field = _normalize_query_field_name(field_name)
        mapped_field = QUERY_FIELD_MAP.get(normalized_field, normalized_field)
        source_values = {}
        for candidate in [mapped_field, normalized_field, field_name]:
            value = row.get(candidate)
            if value in (None, ""):
                continue
            source_values[str(candidate)] = value
        if len(source_values) <= 1:
            continue
        normalized_values = {str(value).strip() for value in source_values.values()}
        if len(normalized_values) > 1:
            conflicts.append(
                {
                    "field": field_name,
                    "mapped_field": mapped_field,
                    "candidate_values": source_values,
                }
            )
    return {
        "has_conflict": bool(conflicts),
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
    }


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
    query_row: dict,
    source_timestamp: str,
) -> dict:
    request_data = _as_dict(request_payload)
    row = _as_dict(query_row)
    price = (
        selected_key_fields.get("price")
        if "price" in selected_key_fields
        else selected_key_fields.get("latest_price", "")
    )
    trade_date = (
        row.get("trade_date")
        or _pick_trade_date_from_source_timestamp(source_timestamp)
        or datetime.now().strftime("%Y-%m-%d")
    )
    return {
        "symbol": str(
            row.get("symbol")
            or request_data.get("stock_code")
            or request_data.get("symbol")
            or ""
        ),
        "name": str(row.get("name") or request_data.get("stock_name") or ""),
        "price": price,
        "trade_date": trade_date,
    }


def _build_data_quality_summary(
    selected_key_fields: dict,
    missing_fields: list,
    source_timestamp: str,
    data_evidences: list = None,
    conflict_summary: dict = None,
) -> dict:
    required_fields = ["price"]
    normalized_selected = {
        _normalize_query_field_name(name): value for name, value in _as_dict(selected_key_fields).items()
    }
    missing_required = [field for field in required_fields if field not in normalized_selected]
    quality_score = 100
    if missing_fields:
        quality_score -= min(len(missing_fields) * 12, 40)
    if missing_required:
        quality_score -= 35
    if not source_timestamp:
        quality_score -= 10
    conflict_meta = _as_dict(conflict_summary)
    if conflict_meta.get("has_conflict"):
        quality_score -= min(int(conflict_meta.get("conflict_count", 0)) * 10, 30)
    evidence_count = len(_as_list(data_evidences))
    if evidence_count == 0:
        quality_score -= 25
    return {
        "provider": "eastmoney_query",
        "required_fields": required_fields,
        "missing_required_fields": missing_required,
        "missing_fields": list(missing_fields),
        "source_timestamp_present": bool(source_timestamp),
        "evidence_count": evidence_count,
        "has_field_conflict": bool(conflict_meta.get("has_conflict", False)),
        "field_conflict_count": int(conflict_meta.get("conflict_count", 0) or 0),
        "is_usable": len(missing_required) == 0 and not conflict_meta.get("has_conflict", False),
        "quality_score": max(0, quality_score),
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


def _save_daily_counter(counter: dict) -> bool:
    try:
        _EASTMONEY_COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _EASTMONEY_COUNTER_FILE.open("w", encoding="utf-8") as f:
            json.dump(counter, f, ensure_ascii=False)
        return True
    except Exception as exc:
        LOGGER.warning("持久化东财日配额失败 path=%s err=%s", _EASTMONEY_COUNTER_FILE, str(exc))
        return False


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
        if not _save_daily_counter(counter):
            raise EastmoneyQuotaPersistError("东财接口日配额持久化失败，已阻断本次请求以避免配额失真")
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
    if not meta.get("success", False):
        return _build_standard_error(
            code=STANDARD_ERROR_CODE_INTERNAL_ERROR,
            message=meta.get("message") or "东方财富资讯检索失败",
            retryable=True,
            details={"response_meta": meta, "request_payload": _desensitize_payload(request_payload or {})},
            meta={"provider": "eastmoney", "endpoint": "news-search", **meta},
        )
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
        "success": True,
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
    return parse_eastmoney_query_response(resp, request_payload=payload)


def parse_eastmoney_query_response(resp: dict, request_payload: dict = None) -> dict:
    data = resp or {}
    meta = _extract_common_meta(data)
    if not meta.get("success", False):
        blocked_by_guardrail = _detect_large_range_blocked(data)
        return _build_standard_error(
            code=STANDARD_ERROR_CODE_INTERNAL_ERROR,
            message=meta.get("message") or "东方财富结构化查询失败",
            retryable=not blocked_by_guardrail,
            details={
                "response_meta": meta,
                "request_payload": _desensitize_payload(request_payload or {}),
                "blocked_by_guardrail": blocked_by_guardrail,
            },
            meta={"provider": "eastmoney", "endpoint": "query", **meta},
        )
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
    selected_key_fields = _extract_key_fields_from_query_row(base_sample, requested_fields)
    key_fields_provider = "eastmoney_query"
    key_fields_priority = 1
    missing_fields = [field for field in requested_fields if field not in selected_key_fields]
    blocked_by_guardrail = _detect_large_range_blocked(data)
    source_timestamp = _extract_source_timestamp(base_sample, fallback_text=json.dumps(base_sample, ensure_ascii=False))
    data_evidences = _build_data_evidences(base_sample, requested_fields, source_timestamp)
    conflict_summary = _build_field_conflict_summary(base_sample, requested_fields)
    standardized_key_fields = _build_standardized_key_fields(
        request_payload=request_payload or {},
        selected_key_fields=selected_key_fields,
        query_row=base_sample,
        source_timestamp=source_timestamp,
    )
    quality_summary = _build_data_quality_summary(
        selected_key_fields=selected_key_fields,
        missing_fields=missing_fields,
        source_timestamp=source_timestamp,
        data_evidences=data_evidences,
        conflict_summary=conflict_summary,
    )
    data_has_payload = isinstance(data_root, dict) and any(value not in (None, "", [], {}) for value in data_root.values())
    empty_result = not bool(records or data_has_payload)
    return {
        "success": True,
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
        "data_evidences": data_evidences,
        "field_conflict_summary": conflict_summary,
        "model_completion_forbidden": True,
        "supplemental_news_only": True,
        "source_timestamp": source_timestamp,
        "data_quality_summary": quality_summary,
        "blocked_by_guardrail": blocked_by_guardrail,
        "guardrail_tip": EASTMONEY_BLOCKED_RESULT_TIP if blocked_by_guardrail else "",
        "empty_result": empty_result,
    }


def eastmoney_stock_screen(
    conditions: dict = None,
    query_text: str = "",
    sort_by: str = "",
    sort_order: str = "desc",
    limit: int = 50,
    timeout: int = 10,
    retries: int = 1,
    **kwargs,
) -> dict:
    query_alias = str(kwargs.get("query") or "").strip()
    keyword_alias = str(kwargs.get("keyword") or "").strip()
    sort_rule_alias = str(kwargs.get("sort_rule") or "").strip()
    final_query_text = str(query_text or query_alias or keyword_alias).strip()
    compiled_conditions = _compile_stock_screen_conditions(final_query_text)
    merged_conditions = dict(compiled_conditions)
    merged_conditions.update(_as_dict(conditions))
    search_keyword = final_query_text or _build_stock_screen_keyword(merged_conditions)
    final_sort_by = sort_by or sort_rule_alias
    if not search_keyword:
        return _build_standard_error(
            code=STANDARD_ERROR_CODE_INVALID_ARGUMENT,
            message="选股请求缺少有效关键词",
            retryable=False,
            details={"query_text": final_query_text, "conditions": merged_conditions},
            meta={"provider": "eastmoney", "endpoint": "stock-screen"},
        )
    payload = {
        "question": search_keyword,
        "query": search_keyword,
        "keyword": search_keyword,
        "conditions": merged_conditions,
        "sort_by": final_sort_by,
        "sort_order": sort_order,
        "limit": max(min(int(limit or 50), 50), 1),
    }
    resp = post_eastmoney(
        endpoint=EASTMONEY_ENDPOINT_STOCK_SCREEN,
        payload=payload,
        timeout=timeout,
        retries=retries,
    )
    parsed = parse_eastmoney_stock_screen_response(resp, request_payload=payload)
    if parsed.get("success") and parsed.get("empty_result"):
        relaxation_chain = []
        price_only_conditions = {
            key: merged_conditions.get(key)
            for key in ("price_lte", "price_gte")
            if key in merged_conditions
        }
        if price_only_conditions and price_only_conditions != merged_conditions:
            relaxation_chain.append("price_only")
            relaxed_payload = dict(payload)
            relaxed_payload["conditions"] = price_only_conditions
            relaxed_resp = post_eastmoney(
                endpoint=EASTMONEY_ENDPOINT_STOCK_SCREEN,
                payload=relaxed_payload,
                timeout=timeout,
                retries=retries,
            )
            parsed = parse_eastmoney_stock_screen_response(relaxed_resp, request_payload=relaxed_payload)
        if parsed.get("success") and parsed.get("empty_result"):
            relaxation_chain.append("keyword_only")
            relaxed_payload = dict(payload)
            relaxed_payload["conditions"] = {}
            relaxed_resp = post_eastmoney(
                endpoint=EASTMONEY_ENDPOINT_STOCK_SCREEN,
                payload=relaxed_payload,
                timeout=timeout,
                retries=retries,
            )
            parsed = parse_eastmoney_stock_screen_response(relaxed_resp, request_payload=relaxed_payload)
        if parsed.get("success"):
            parsed["relaxation_chain"] = relaxation_chain
    return parsed


def parse_eastmoney_stock_screen_response(resp: dict, request_payload: dict = None) -> dict:
    data = resp or {}
    meta = _extract_common_meta(data)
    if not meta.get("success", False):
        message = meta.get("message") or "东方财富选股请求失败"
        error_code = STANDARD_ERROR_CODE_INVALID_ARGUMENT if "参数校验失败" in message else STANDARD_ERROR_CODE_INTERNAL_ERROR
        blocked_by_guardrail = _detect_large_range_blocked(data)
        details = {
            "response_meta": meta,
            "request_payload": _desensitize_payload(request_payload or {}),
            "blocked_by_guardrail": blocked_by_guardrail,
        }
        return _build_standard_error(
            code=error_code,
            message=message,
            retryable=not blocked_by_guardrail,
            details=details,
            meta={"provider": "eastmoney", "endpoint": "stock-screen", **meta},
        )
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
        "success": True,
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


def _compile_stock_screen_conditions(query_text: str) -> dict:
    text = str(query_text or "").strip()
    if not text:
        return {}
    conditions = {}
    lower_text = text.lower()
    match_lte = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*元?\s*(?:以下|以内|低于|不高于|<=)", text)
    if match_lte:
        conditions["price_lte"] = float(match_lte.group(1))
    match_gte = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*元?\s*(?:以上|高于|不少于|>=)", text)
    if match_gte:
        conditions["price_gte"] = float(match_gte.group(1))
    if "低价股" in text and "price_lte" not in conditions:
        conditions["price_lte"] = 10.0
    if "高增长" in text or "成长" in text:
        conditions["growth_hint"] = "high_growth"
    if "量价齐升" in text:
        conditions["volume_price_trend"] = "up"
    if "主力净流入" in text or "资金流入" in text:
        conditions["main_net_inflow"] = "positive"
    if "换手率" in text:
        conditions["turnover_focus"] = True
    if "市盈率" in text and "低" in text:
        conditions["pe_ttm_trend"] = "low"
    if "st" in lower_text:
        conditions["include_st"] = True
    return conditions


def _build_stock_screen_keyword(conditions: dict) -> str:
    fields = _as_dict(conditions)
    if not fields:
        return ""
    if "price_lte" in fields and float(fields.get("price_lte") or 0) > 0:
        return f"{fields.get('price_lte')}元以下低价股"
    if fields.get("growth_hint") == "high_growth":
        return "高增长选股"
    if fields.get("volume_price_trend") == "up":
        return "量价齐升选股"
    return "A股选股"


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


def estimate_main_cost(
    main_net_inflow: float,
    turnover_rate: float,
    current_price: float,
) -> dict:
    """
    估算主力持仓成本区间。

    原理：
        主力净流入金额 ＝ 主力买入额 - 主力卖出额
        换手率 ＝ 成交量 / 流通股本  →  流通股本 ≈ 成交量 / 换手率
        主力估算持仓量 ＝ |净流入额| / 当前股价
        主力持仓成本 ＝ |净流入额| / 估算持仓量
                              ＝ |净流入额| × 换手率 / 成交量
                              ≈ |净流入额| × 换手率 / (成交量/股价)
                              ＝ |净流入额| × 换手率 × 股价 / 成交量

    由于成交量数据难以直接获取，改用简化公式：
        主力成本 ≈ |净流入额| × 换手率 / (换手率 × 流通股本) × 当前股价
        ≈ |净流入额| × 换手率² / 成交额占比  （定性估算）

    更实用的方式：用净流入额和换手率的比值做定性区间：
        - 净流入大 + 换手率适中 → 主力控盘能力强，成本区间清晰
        - 净流入大 + 换手率极高 → 可能是对倒，成本估算参考价值低

    参数:
        main_net_inflow: 主力净流入额（元，正数=净买入，负数=净卖出）
        turnover_rate: 换手率（小数，如 0.05 表示 5%，注意兼容百分数字符串如 "5.0"）
        current_price: 当前股价（元）

    返回:
        dict，含成本估算值、偏离度、置信度标签
    """
    if current_price <= 0:
        return {
            "cost_estimate": None,
            "deviation_pct": None,
            "confidence": "low",
            "signal": "数据不足，无法估算",
        }

    # 统一换手率格式（兼容 "5.0" 百分数字符串）
    if isinstance(turnover_rate, str):
        tr_str = turnover_rate.strip().replace("%", "")
        try:
            tr_val = float(tr_str)
        except ValueError:
            return {
                "cost_estimate": None,
                "deviation_pct": None,
                "confidence": "low",
                "signal": "换手率格式异常",
            }
        # 如果 > 1 认为是百分数
        turnover = tr_val / 100 if tr_val > 1 else tr_val
    elif isinstance(turnover_rate, (int, float)):
        # 换手率可能是小数（0.05）也可能是百分数（5）
        turnover = turnover_rate / 100 if turnover_rate > 1 else turnover_rate
    else:
        return {
            "cost_estimate": None,
            "deviation_pct": None,
            "confidence": "low",
            "signal": "换手率格式异常",
        }

    if turnover <= 0:
        return {
            "cost_estimate": None,
            "deviation_pct": None,
            "confidence": "low",
            "signal": "换手率必须大于0",
        }

    inflow_abs = abs(main_net_inflow)
    inflow_yuan = main_net_inflow / 100_000_000  # 亿元（正=净买入，负=净卖出）
    if inflow_abs <= 0:
        return {
            "cost_estimate": None,
            "deviation_pct": None,
            "confidence": "low",
            "signal": "无主力净流入数据",
        }

    # 简化估算：主力成本 ≈ |净流入| × 换手率 / 成交量（定性）
    # 用"净流入额/当前股价"代表主力大致持仓金额，再除以换手率得到持仓量级
    # 持仓量级 × 当前股价 = 持仓市值  →  成本 = |净流入| / 持仓占比
    # 简化：主力成本 ≈ 当前价 × (1 - 净流入占比)
    # 净流入占比 = |净流入| / (换手率 × 估算流通市值)  ≈ |净流入| / (换手率 × 成交额/换手率)
    # 这里用定性判断：
    # 高置信度条件：换手率在 3%~25% 区间（过低无意义，过高对倒嫌疑）

    if 0.03 <= turnover <= 0.25:
        # 估算主力持仓比例 ≈ |净流入| / (换手率 × 估算流通盘)
        # 成交额 = 成交量 × 均价 ≈ 成交量 × 当前价
        # 换手率 = 成交量 / 流通股本  →  成交量 ≈ 换手率 × 流通股本
        # 流通股本 ≈ 成交额 / 换手率 / 当前价
        # 但我们没有成交额，改用定性方法：
        # 主力成本 ≈ 当前价 × (1 - |净流入|/成交额占比)  （定性）
        # 简化版：用换手率和净流入构造定性区间
        cost_low = current_price * (1 - turnover * 2)   # 低估：换手放大
        cost_high = current_price * (1 - turnover * 0.5)  # 高估：换手保守
        cost_estimate = (cost_low + cost_high) / 2
        deviation_pct = (current_price - cost_estimate) / cost_estimate * 100
        confidence = "medium"
        if inflow_abs > 1_000_000_000:  # 亿以上净流入
            confidence = "high"
        elif inflow_abs < 100_000_000:   # 亿以下
            confidence = "low"
    else:
        cost_estimate = current_price * 0.9 if main_net_inflow < 0 else current_price * 1.1
        deviation_pct = (current_price - cost_estimate) / cost_estimate * 100
        confidence = "low"
        if turnover < 0.03:
            signal = f"换手率偏低({turnover*100:.1f}%)，成本估算置信度低"
        else:
            signal = f"换手率偏高({turnover*100:.1f}%)，可能存在对倒，估算参考性差"
        return {
            "cost_estimate": round(cost_estimate, 2),
            "cost_low": None,
            "cost_high": None,
            "deviation_pct": round(deviation_pct, 2),
            "confidence": confidence,
            "main_inflow_yuan": round(inflow_yuan, 2),
            "turnover_pct": round(turnover * 100, 2),
            "signal": signal,
        }

    # 判断信号
    if main_net_inflow < 0:
        # 主力净卖出场景
        if deviation_pct > 10:
            signal = f"主力已出货，当前价高于其成本{deviation_pct:.1f}%，机构可能看空后势"
        elif deviation_pct < -10:
            signal = f"主力在高位出货后股价下跌，当前价低于其成本{abs(deviation_pct):.1f}%，注意接飞刀风险"
        else:
            signal = f"主力有出货迹象，股价与主力成本偏离{deviation_pct:.1f}%，观望为主"
    else:
        # 主力净买入场景
        if deviation_pct > 10:
            signal = f"当前价高于主力成本{deviation_pct:.1f}%，主力浮盈较大，注意获利回吐风险"
        elif deviation_pct < -10:
            signal = f"当前价低于主力成本{abs(deviation_pct):.1f}%，主力浮亏，短期关注支撑"
        else:
            signal = f"当前价接近主力成本，偏离{deviation_pct:.1f}%，安全区间"

    return {
        "cost_estimate": round(cost_estimate, 2),
        "cost_low": round(max(0.01, cost_low), 2),
        "cost_high": round(cost_high, 2),
        "deviation_pct": round(deviation_pct, 2),
        "confidence": confidence,
        "main_inflow_yuan": round(inflow_yuan, 2),
        "turnover_pct": round(turnover * 100, 2),
        "signal": signal,
    }


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
        {
            "priority": "建议",
            "indicator": "主力成本估算",
            "data_source": "主力净流入额、换手率、当前股价",
            "trigger_rule": "主力净流入>1亿且换手率3%~25%时触发，输出成本区间与偏离度",
            "collect_entry": "stock_utils.get_search_queries",
            "calc_entry": "stock_utils.estimate_main_cost",
            "route_entry": "team_router.build_shortline_supervisor_rules",
            "output_entry": "generate_report._build_main_cost_signal",
            "report_position": "资金面/主力成本区间",
            "risk": "换手率<3%或>25%时置信度低；不作为买卖唯一依据",
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
