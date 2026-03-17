import hashlib
import json
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from stock_utils import (
    normalize_stock_name,
    validate_stock_code,
)


TEAM_TRIGGER_KEYWORDS = [
    "对比",
    "验证",
    "复盘",
    "冲突",
    "分歧",
    "组合",
    "股票池",
    "候选",
    "多股",
    "短线指标",
    "指标增强",
    "推荐",
    "筛选",
    "审计",
]

HIGH_INTENT_STAGE_KEYWORDS = {
    "data_collect": ["今日", "当日", "实时", "最新", "采集", "收集", "抓取"],
    "screening": ["筛选", "选股", "候选", "股票池"],
    "expert_discussion": ["专家讨论", "讨论", "会诊", "辩论", "交叉质疑"],
    "recommendation": ["推荐", "建议", "优选"],
}

HIGH_INTENT_MIN_SCREENING_COUNT = 10
HIGH_INTENT_MIN_RECOMMEND_COUNT = 3
INTENT_CACHE_TTL_SECONDS = 300
INTENT_DUPLICATE_WINDOW_SECONDS = 120
INTENT_DUPLICATE_THRESHOLD = 3
INTENT_REQUEST_LIMIT_MAX = 50
INTENT_TIME_RANGE_MAX_DAYS = 180
_INTENT_CACHE_FILE = Path(__file__).resolve().parent / ".team_router_intent_cache.json"
_INTENT_ROUTE_LOG_FILE = Path(__file__).resolve().parent / ".team_router_intent_routes.json"
_INTENT_LOCK = threading.Lock()
_INTENT_RUNTIME_FALLBACK: dict = {}
_INTENT_PRIORITY = {
    "stock-screen": 3,
    "query": 2,
    "news-search": 1,
}
INTENT_KEYWORDS = {
    "news-search": ["资讯", "新闻", "快讯", "公告", "研报", "舆情", "事件驱动"],
    "query": ["行情", "资金流向", "财务", "估值", "指标", "主力净流入", "成交额"],
    "stock-screen": ["选股", "筛选", "股票池", "低价股", "高增长", "量价齐升", "策略筛选"],
}
FAILURE_REASON_CODE_REQUEST_LIMIT_EXCEEDED = "REQUEST_LIMIT_EXCEEDED"
FAILURE_REASON_CODE_TIME_RANGE_EXCEEDED = "TIME_RANGE_EXCEEDED"
FAILURE_REASON_CODE_TARGET_REQUIRED = "TARGET_REQUIRED"
FAILURE_REASON_CODE_INTENT_NOT_MATCHED = "INTENT_NOT_MATCHED"
FAILURE_REASON_CODE_DUPLICATE_REQUEST = "DUPLICATE_REQUEST"
FAILURE_REASON_CODE_SYMBOL_METADATA_UNAVAILABLE = "SYMBOL_METADATA_UNAVAILABLE"
FAILURE_REASON_TIPS = {
    FAILURE_REASON_CODE_REQUEST_LIMIT_EXCEEDED: "请降低返回条数（建议<=50）后重试。",
    FAILURE_REASON_CODE_TIME_RANGE_EXCEEDED: "请缩小时间范围（建议<=180天）后重试。",
    FAILURE_REASON_CODE_TARGET_REQUIRED: "请补充股票代码或股票名称后再发起请求。",
    FAILURE_REASON_CODE_INTENT_NOT_MATCHED: "未识别到东财意图，已降级为本地分析流程。",
    FAILURE_REASON_CODE_DUPLICATE_REQUEST: "请求过于频繁，请稍后重试或补充差异化筛选条件。",
    FAILURE_REASON_CODE_SYMBOL_METADATA_UNAVAILABLE: "缺少可用股票代码，已降级为东财/本地流程。",
}

PRECONFIGURED_EXPERT_AGENTS = {
    "run_data_auditor": "stock-data-auditor",
    "run_fundamental_expert": "stock-fundamental-expert",
    "run_technical_expert": "stock-technical-expert",
    "run_quant_flow_expert": "stock-quant-flow-expert",
    "run_risk_expert": "stock-risk-expert",
    "run_macro_expert": "stock-macro-expert",
    "run_industry_researcher_expert": "stock-industry-researcher",
    "run_event_hunter_expert": "stock-event-hunter",
    "run_expert_identifier_agent": "stock-identity-auditor",
}


def _append_reason(reasons: list, reason: str) -> None:
    if reason and reason not in reasons:
        reasons.append(reason)


def should_use_agent_team(user_request: str) -> dict:
    request = (user_request or "").strip()
    normalized_request = _normalize_request(request)
    eastmoney_router = route_eastmoney_intent(request)
    reasons = []
    execution_profile = "lite_parallel"
    stock_codes = re.findall(r"\b[036]\d{5}\b", request)
    if len(set(stock_codes)) >= 2:
        _append_reason(reasons, "多标的")
    if "多股" in request or "股票池" in request:
        _append_reason(reasons, "多标的")
    if _looks_like_multi_target_by_names(normalized_request):
        _append_reason(reasons, "多标的")
    if any(keyword in request for keyword in TEAM_TRIGGER_KEYWORDS):
        _append_reason(reasons, "验证")
    if "短线" in request and "指标" in request:
        _append_reason(reasons, "指标增强")
    high_intent = _match_high_intent_pipeline(normalized_request)
    if high_intent.get("matched"):
        _append_reason(reasons, "高意图串联任务")
        _append_reason(reasons, "复杂请求")
        execution_profile = "full_parallel"
        screening_count = high_intent.get("screening_count")
        recommend_count = high_intent.get("recommend_count")
        if screening_count:
            _append_reason(reasons, f"{screening_count}支筛选")
        if recommend_count:
            _append_reason(reasons, f"{recommend_count}支推荐")
    if not reasons:
        _append_reason(reasons, "Team-First默认")
    if execution_profile != "full_parallel" and _is_complex_team_request(normalized_request):
        execution_profile = "full_parallel"
        _append_reason(reasons, "复杂请求")
    return {
        "use_team": True,
        "reasons": reasons,
        "execution_profile": execution_profile,
        "eastmoney_router": eastmoney_router,
    }


def build_skill_chain_plan(use_team: bool) -> dict:
    if not use_team:
        return {
            "mode": "agent_team",
            "execution_profile": "lite_parallel",
            "steps": [
                "run_data_auditor",
                "collect_data",
                "run_fundamental_expert",
                "run_technical_expert",
                "run_quant_flow_expert",
                "run_risk_expert",
                "run_expert_identifier_agent",
                "supervisor_review",
                "render_report",
            ],
            "team_rules": build_shortline_supervisor_rules(),
        }
    return {
        "mode": "agent_team",
        "execution_profile": "full_parallel",
        "steps": [
            "run_data_auditor",
            "collect_data",
            "run_fundamental_expert",
            "run_technical_expert",
            "run_quant_flow_expert",
            "run_risk_expert",
            "run_macro_expert",
            "run_industry_researcher_expert",
            "run_event_hunter_expert",
            "run_expert_identifier_agent",
            "supervisor_review",
            "render_report",
        ],
        "team_rules": build_shortline_supervisor_rules(),
    }


def build_shortline_supervisor_rules() -> dict:
    return {
        "team_required_requests": [
            "多标的对比",
            "历史验证/复盘",
            "冲突仲裁",
            "短线指标增强请求",
            "今日采集+10支筛选+专家讨论+3支推荐",
        ],
        "high_intent_activation": {
            "required_stages": ["data_collect", "screening", "expert_discussion", "recommendation"],
            "screening_min_count": HIGH_INTENT_MIN_SCREENING_COUNT,
            "recommendation_min_count": HIGH_INTENT_MIN_RECOMMEND_COUNT,
        },
        "expert_assignments": {
            "run_data_auditor": ["field_timestamp_check", "source_consistency_check", "freshness_gate"],
            "run_technical_expert": ["vwap_deviation", "atr_stop", "breakout_retest"],
            "run_quant_flow_expert": ["volume_ratio", "fund_slope", "reversal_detection"],
            "run_industry_researcher_expert": ["industry_cycle", "supply_chain_signal", "competition_map"],
            "run_event_hunter_expert": ["policy_event_scan", "announcement_impact", "regulatory_signal"],
            "run_expert_identifier_agent": ["agent_identity_match", "stock_code_match", "price_consistency_check"],
        },
        "supervisor_review_fields": [
            "audit_gate",
            "expert_identity_gate",
            "process_block",
            "indicator_signals",
            "indicator_missing",
            "downgrade_reason",
            "industry_research_output",
            "event_hunter_output",
            "conflict_items",
            "arbitration_result",
            "evidences",
        ],
        "expert_output_schema": {
            "run_industry_researcher_expert": _build_industry_researcher_schema(),
            "run_event_hunter_expert": _build_event_hunter_schema(),
            "run_expert_identifier_agent": _build_expert_identifier_schema(),
        },
        "expert_agent_map": dict(PRECONFIGURED_EXPERT_AGENTS),
        "expert_agent_registry": resolve_preconfigured_expert_agents(),
        "conflict_arbitration_rules": [
            "行业景气正向但事件冲击为强负向时，主管将标签上限降为观察",
            "行业景气负向且事件冲击负向时，主管将标签上限降为回避",
            "行业景气与事件冲击同向时，保留原标签并提高执行置信度",
        ],
        "downgrade_policy": {
            "missing_any": ["vwap_deviation", "atr_stop", "volume_ratio"],
            "max_label_after_missing": "观察",
            "confidence_cap": "中",
        },
        "continuity_guard": {
            "parallel_strategy": "strict_fanout_join",
            "single_flow_fallback": False,
            "failure_policy": "isolate_and_continue",
            "retry_policy": {"max_retries": 2, "backoff": "exponential"},
            "required_deliverables": ["team_consensus", "conflict_items", "final_recommendations"],
        },
        "eastmoney_intent_router": {
            "intents": list(INTENT_KEYWORDS.keys()),
            "intent_keywords": dict(INTENT_KEYWORDS),
            "critical_gate": {
                "request_limit_max": INTENT_REQUEST_LIMIT_MAX,
                "time_range_max_days": INTENT_TIME_RANGE_MAX_DAYS,
                "duplicate_window_seconds": INTENT_DUPLICATE_WINDOW_SECONDS,
                "duplicate_threshold": INTENT_DUPLICATE_THRESHOLD,
            },
            "local_persistence": {
                "cache_file": str(_INTENT_CACHE_FILE),
                "route_log_file": str(_INTENT_ROUTE_LOG_FILE),
                "runtime_fallback": True,
            },
        },
        "fixed_steps": [
            "run_data_auditor",
            "collect_data",
            "run_fundamental_expert",
            "run_technical_expert",
            "run_quant_flow_expert",
            "run_risk_expert",
            "run_macro_expert",
            "run_industry_researcher_expert",
            "run_event_hunter_expert",
            "run_expert_identifier_agent",
            "supervisor_review",
            "render_report",
        ],
    }


def resolve_preconfigured_expert_agents() -> dict:
    agents_root = Path(__file__).resolve().parent.parent / "agents"
    registry = {}
    for step, agent_name in PRECONFIGURED_EXPERT_AGENTS.items():
        agent_file = agents_root / f"{agent_name}.md"
        exists = agent_file.exists()
        registry[step] = {
            "agent_name": agent_name,
            "source": "preconfigured" if exists else "default",
            "agent_file": str(agent_file) if exists else "",
        }
    return registry


def route_eastmoney_intent(user_request: str, stock_code: str = "", stock_name: str = "") -> dict:
    request = (user_request or "").strip()
    normalized = _normalize_request(request)
    route = _classify_eastmoney_intent(normalized)
    gate = _build_critical_gate(route, normalized, stock_code=stock_code, stock_name=stock_name)
    cache_result = _apply_intent_cache(route, gate, normalized)
    resolved_identity = _resolve_stock_identity_for_router(stock_code, stock_name, request)
    metadata_passthrough = _build_metadata_passthrough_meta(
        resolved_identity.get("stock_code", ""),
        resolved_identity.get("stock_name", ""),
    )
    metadata_passthrough["symbol_resolved_via"] = resolved_identity.get("resolution_source", "")
    metadata_passthrough["resolution_trace"] = resolved_identity.get("resolution_trace", [])
    if not metadata_passthrough.get("validation_passed", True):
        if metadata_passthrough.get("failure_code"):
            _append_guardrail_failure(
                gate,
                code=metadata_passthrough.get("failure_code"),
                message=metadata_passthrough.get("validation_conclusion", "标的元信息校验未通过"),
            )
    fallback_mode = (
        gate.get("blocked_by_guardrail")
        or route.get("intent_category", "none") == "none"
    )
    route_result = {
        "request": request,
        "normalized_request": normalized,
        "intent_category": route.get("intent_category", "none"),
        "endpoint": route.get("endpoint", ""),
        "matched_keywords": route.get("matched_keywords", []),
        "intent_confidence": route.get("intent_confidence", 0.0),
        "critical_gate": gate,
        "metadata_passthrough": metadata_passthrough,
        "cache": cache_result,
        "fallback_mode": bool(fallback_mode),
        "websearch_fallback_forbidden": False,
        "local_saved": False,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    route_result["local_saved"] = _persist_route_result(route_result)
    return route_result


def _classify_eastmoney_intent(request: str) -> dict:
    if not request:
        return {"intent_category": "none", "endpoint": "", "matched_keywords": [], "intent_confidence": 0.0}
    score_map = {}
    matched_map = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        matched_keywords = [keyword for keyword in keywords if keyword in request]
        matched_map[intent] = matched_keywords
        score_map[intent] = len(matched_keywords)
    top_score = max(score_map.values()) if score_map else 0
    if top_score <= 0:
        return {"intent_category": "none", "endpoint": "", "matched_keywords": [], "intent_confidence": 0.0}
    candidates = [intent for intent, score in score_map.items() if score == top_score]
    intent = sorted(candidates, key=lambda item: _INTENT_PRIORITY.get(item, 0), reverse=True)[0]
    confidence = min(1.0, top_score / max(len(INTENT_KEYWORDS.get(intent, [])), 1))
    return {
        "intent_category": intent,
        "endpoint": intent,
        "matched_keywords": matched_map.get(intent, []),
        "intent_confidence": round(confidence, 3),
    }


def _build_critical_gate(route: dict, request: str, stock_code: str = "", stock_name: str = "") -> dict:
    reasons = []
    reason_codes = []
    user_tips = []
    blocked = False
    requested_limit = _extract_request_limit(request)
    requested_days = _extract_time_range_days(request)
    intent = route.get("intent_category", "none")
    if requested_limit and requested_limit > INTENT_REQUEST_LIMIT_MAX:
        blocked = True
        _append_guardrail_failure(
            gate={"reasons": reasons, "reason_codes": reason_codes, "user_tips": user_tips},
            code=FAILURE_REASON_CODE_REQUEST_LIMIT_EXCEEDED,
            message=f"返回数量超限({requested_limit}>{INTENT_REQUEST_LIMIT_MAX})",
        )
    if requested_days and requested_days > INTENT_TIME_RANGE_MAX_DAYS:
        blocked = True
        _append_guardrail_failure(
            gate={"reasons": reasons, "reason_codes": reason_codes, "user_tips": user_tips},
            code=FAILURE_REASON_CODE_TIME_RANGE_EXCEEDED,
            message=f"时间范围超限({requested_days}>{INTENT_TIME_RANGE_MAX_DAYS}天)",
        )
    has_target = bool(stock_code) or bool(stock_name) or bool(re.findall(r"(?<!\d)[036]\d{5}(?!\d)", request))
    if intent in {"news-search", "query"} and not has_target:
        blocked = True
        _append_guardrail_failure(
            gate={"reasons": reasons, "reason_codes": reason_codes, "user_tips": user_tips},
            code=FAILURE_REASON_CODE_TARGET_REQUIRED,
            message="缺少标的约束(股票代码/名称)",
        )
    if intent == "none":
        _append_guardrail_failure(
            gate={"reasons": reasons, "reason_codes": reason_codes, "user_tips": user_tips},
            code=FAILURE_REASON_CODE_INTENT_NOT_MATCHED,
            message="未命中东财意图，降级本地流程",
        )
    return {
        "passed": not blocked,
        "blocked_by_guardrail": blocked,
        "reasons": reasons,
        "reason_codes": reason_codes,
        "user_tips": user_tips,
        "requested_limit": requested_limit,
        "requested_time_range_days": requested_days,
        "fallback_action": "use_local_analysis_only" if blocked or intent == "none" else "allow_external_call",
    }


def _extract_request_limit(request: str) -> int:
    if not request:
        return 0
    matches = re.findall(r"([0-9]{1,3})\s*(?:支|只|条|个)", request)
    if not matches:
        return 0
    return max(int(item) for item in matches)


def _extract_time_range_days(request: str) -> int:
    if not request:
        return 0
    max_days = 0
    for value in re.findall(r"近\s*([0-9]{1,4})\s*日", request):
        max_days = max(max_days, int(value))
    for value in re.findall(r"([0-9]{1,4})\s*天", request):
        max_days = max(max_days, int(value))
    for value in re.findall(r"([0-9]{1,3})\s*周", request):
        max_days = max(max_days, int(value) * 7)
    for value in re.findall(r"([0-9]{1,3})\s*月", request):
        max_days = max(max_days, int(value) * 30)
    for value in re.findall(r"([0-9]{1,2})\s*年", request):
        max_days = max(max_days, int(value) * 365)
    return max_days


def _apply_intent_cache(route: dict, gate: dict, normalized_request: str) -> dict:
    now = datetime.now()
    cache_key = _build_intent_cache_key(normalized_request)
    with _INTENT_LOCK:
        cache_payload = _load_json_file(_INTENT_CACHE_FILE, default={"items": {}})
        items = cache_payload.get("items", {})
        cached = items.get(cache_key, {})
        _cleanup_intent_cache(items, now)
        if cached and _is_cache_alive(cached, now):
            cached_response = dict(cached.get("response", {}))
            cache_hit = True
            hit_count = int(cached.get("hit_count", 0)) + 1
            first_seen = _parse_cache_time(cached.get("first_seen")) or now
            duplicate_threshold_triggered = (
                hit_count > INTENT_DUPLICATE_THRESHOLD
                and (now - first_seen) <= timedelta(seconds=INTENT_DUPLICATE_WINDOW_SECONDS)
            )
            if duplicate_threshold_triggered:
                gate["passed"] = False
                gate["blocked_by_guardrail"] = True
                gate["fallback_action"] = "use_local_analysis_only"
                _append_guardrail_failure(
                    gate=gate,
                    code=FAILURE_REASON_CODE_DUPLICATE_REQUEST,
                    message=f"命中重复请求阈值({hit_count}>{INTENT_DUPLICATE_THRESHOLD})",
                )
            items[cache_key] = {
                "key": cache_key,
                "request": normalized_request,
                "created_at": cached.get("created_at", _now_text(now)),
                "first_seen": cached.get("first_seen", _now_text(now)),
                "updated_at": _now_text(now),
                "hit_count": hit_count,
                "response": cached_response,
            }
            _save_json_file(_INTENT_CACHE_FILE, {"items": items})
            return {
                "key": cache_key,
                "cache_hit": cache_hit,
                "dedup_hit": True,
                "duplicate_threshold_triggered": duplicate_threshold_triggered,
                "hit_count": hit_count,
            }
        items[cache_key] = {
            "key": cache_key,
            "request": normalized_request,
            "created_at": _now_text(now),
            "first_seen": _now_text(now),
            "updated_at": _now_text(now),
            "hit_count": 1,
            "response": {"intent_category": route.get("intent_category", "none"), "gate_passed": gate.get("passed", False)},
        }
        _save_json_file(_INTENT_CACHE_FILE, {"items": items})
    return {
        "key": cache_key,
        "cache_hit": False,
        "dedup_hit": False,
        "duplicate_threshold_triggered": False,
        "hit_count": 1,
    }


def _cleanup_intent_cache(items: dict, now: datetime) -> None:
    expired_keys = []
    for key, value in items.items():
        updated_at = _parse_cache_time(value.get("updated_at"))
        if not updated_at or (now - updated_at).total_seconds() > INTENT_CACHE_TTL_SECONDS:
            expired_keys.append(key)
    for key in expired_keys:
        items.pop(key, None)


def _build_intent_cache_key(request: str) -> str:
    return hashlib.sha256((request or "").encode("utf-8")).hexdigest()


def _append_guardrail_failure(gate: dict, code: str, message: str) -> None:
    if not isinstance(gate, dict):
        return
    reasons = gate.setdefault("reasons", [])
    reason_codes = gate.setdefault("reason_codes", [])
    user_tips = gate.setdefault("user_tips", [])
    if message and message not in reasons:
        reasons.append(message)
    if code and code not in reason_codes:
        reason_codes.append(code)
    tip = FAILURE_REASON_TIPS.get(code, "")
    if tip and tip not in user_tips:
        user_tips.append(tip)


def _resolve_stock_code_for_router(stock_code: str, request: str) -> str:
    explicit = (stock_code or "").strip()
    if validate_stock_code(explicit):
        return explicit
    matched = re.findall(r"(?<!\d)[036]\d{5}(?!\d)", request or "")
    return matched[0] if matched else ""


def _resolve_stock_identity_for_router(stock_code: str, stock_name: str, request: str) -> dict:
    resolved_code = _resolve_stock_code_for_router(stock_code, request)
    normalized_name = normalize_stock_name(stock_name) if stock_name else ""
    trace = []
    if resolved_code:
        trace.append("explicit_or_regex_code")
        return {
            "stock_code": resolved_code,
            "stock_name": normalized_name or (stock_name or "").strip(),
            "resolution_source": "code",
            "resolution_trace": trace,
        }
    if not normalized_name:
        trace.append("missing_name")
        return {
            "stock_code": "",
            "stock_name": "",
            "resolution_source": "",
            "resolution_trace": trace,
        }
    trace.append("name_only_without_symbol")
    return {
        "stock_code": "",
        "stock_name": normalized_name,
        "resolution_source": "name",
        "resolution_trace": trace,
    }


def _build_metadata_passthrough_meta(stock_code: str, stock_name: str = "") -> dict:
    fetched_at = _now_text()
    base = {
        "provider": "eastmoney",
        "source_function": "stock_utils.eastmoney_query",
        "fetched_at": fetched_at,
        "symbol": stock_code or "",
        "stock_name": (stock_name or "").strip(),
        "validation_passed": True,
        "validation_conclusion": "东财标的元信息校验通过",
        "failure_code": "",
        "failure_message": "",
        "meta": {},
    }
    if not stock_code:
        base["validation_passed"] = False
        base["validation_conclusion"] = "缺少合法股票代码，无法执行结构化关键字段校验"
        base["failure_code"] = FAILURE_REASON_CODE_SYMBOL_METADATA_UNAVAILABLE
        base["failure_message"] = "missing_stock_code"
        return base
    base["quote_snapshot"] = {
        "symbol": stock_code,
        "name": (stock_name or "").strip(),
        "last_price": "",
        "change_percent": "",
    }
    return base


def _is_cache_alive(cache_item: dict, now: datetime) -> bool:
    updated_at = _parse_cache_time(cache_item.get("updated_at"))
    if not updated_at:
        return False
    return (now - updated_at).total_seconds() <= INTENT_CACHE_TTL_SECONDS


def _parse_cache_time(text: str):
    raw = (text or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _persist_route_result(route_result: dict) -> bool:
    payload = _load_json_file(_INTENT_ROUTE_LOG_FILE, default={"routes": []})
    routes = payload.get("routes", [])
    routes.append(route_result)
    if len(routes) > 200:
        routes = routes[-200:]
    payload["routes"] = routes
    ok = _save_json_file(_INTENT_ROUTE_LOG_FILE, payload)
    if not ok:
        _INTENT_RUNTIME_FALLBACK["last_route"] = dict(route_result)
    return ok


def _load_json_file(file_path: Path, default: Any = None) -> dict:
    if not file_path.exists():
        return default if isinstance(default, dict) else {}
    try:
        with file_path.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
            return loaded if isinstance(loaded, dict) else (default if isinstance(default, dict) else {})
    except Exception:
        return default if isinstance(default, dict) else {}


def _save_json_file(file_path: Path, payload: dict) -> bool:
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        return True
    except Exception:
        return False


def _now_text(now: datetime = None) -> str:
    current = now or datetime.now()
    return current.strftime("%Y-%m-%d %H:%M:%S")


def _build_industry_researcher_schema() -> dict:
    return {
        "agent": "expert_industry_researcher",
        "required_input_fields": ["stock_code", "stock_name", "industry", "news", "as_of"],
        "required_output_fields": [
            "景气结论",
            "景气拐点",
            "竞争格局",
            "驱动因子",
            "风险提示",
            "decision_hint",
            "evidences",
        ],
        "evidence_schema": ["conclusion", "value", "source_url", "timestamp"],
    }


def _build_event_hunter_schema() -> dict:
    return {
        "agent": "expert_event_hunter",
        "required_input_fields": ["stock_code", "stock_name", "news", "announcement", "policy_event", "as_of"],
        "required_output_fields": [
            "事件方向",
            "冲击强度",
            "时效窗口",
            "监管信号",
            "action_hint",
            "decision_hint",
            "evidences",
        ],
        "evidence_schema": ["conclusion", "value", "source_url", "timestamp"],
    }


def _build_expert_identifier_schema() -> dict:
    return {
        "agent": "expert_identifier_agent",
        "required_input_fields": ["stock_code", "price_info", "expert_outputs", "field_sources"],
        "required_output_fields": [
            "passed",
            "identity_passed",
            "price_passed",
            "require_block",
            "failed_agents",
            "failed_reasons",
            "next_action",
        ],
    }


def _looks_like_multi_target_by_names(request: str) -> bool:
    if not request:
        return False
    if not any(separator in request for separator in ["和", "、", "及", ",", "，"]):
        return False
    if not any(keyword in request for keyword in ["分析", "对比", "评估", "建议"]):
        return False
    candidate_tokens = re.findall(r"[\u4e00-\u9fa5]{2,8}", request)
    return len(candidate_tokens) >= 3


def _is_complex_team_request(request: str) -> bool:
    if not request:
        return False
    complexity_keywords = ["收集", "采集", "今日", "筛选", "推荐", "讨论", "验证", "复盘", "对比", "股票池", "候选"]
    hit_count = sum(1 for keyword in complexity_keywords if keyword in request)
    return hit_count >= 3


def _normalize_request(request: str) -> str:
    if not request:
        return ""
    normalized = re.sub(r"[+\-_/|｜、，,；;：:]+", " ", request)
    return re.sub(r"\s+", " ", normalized).strip()


def _match_high_intent_pipeline(request: str) -> dict:
    if not request:
        return {"matched": False}
    stage_hits = {
        "data_collect": _has_all_keywords(request, ["今日"], ["采集", "收集", "抓取", "获取"]),
        "screening": _has_any_keyword(request, HIGH_INTENT_STAGE_KEYWORDS["screening"]),
        "expert_discussion": _has_any_keyword(request, HIGH_INTENT_STAGE_KEYWORDS["expert_discussion"]),
        "recommendation": _has_any_keyword(request, HIGH_INTENT_STAGE_KEYWORDS["recommendation"]),
    }
    screening_count = _extract_quantified_count(request, ["筛选", "选股", "候选"])
    recommend_count = _extract_quantified_count(request, ["推荐", "建议", "优选"])
    count_ready = (
        screening_count is not None
        and recommend_count is not None
        and screening_count >= HIGH_INTENT_MIN_SCREENING_COUNT
        and recommend_count >= HIGH_INTENT_MIN_RECOMMEND_COUNT
    )
    matched = all(stage_hits.values()) and count_ready
    return {
        "matched": matched,
        "stage_hits": stage_hits,
        "screening_count": screening_count,
        "recommend_count": recommend_count,
    }


def _extract_quantified_count(request: str, nearby_keywords: list) -> int | None:
    if not request:
        return None
    number_pattern = re.compile(r"([0-9]{1,3}|[一二三四五六七八九十两]{1,3})\s*[只支个]")
    for match in number_pattern.finditer(request):
        value = _to_int(match.group(1))
        if value is None:
            continue
        start = max(match.start() - 8, 0)
        end = min(match.end() + 8, len(request))
        window = request[start:end]
        if any(keyword in window for keyword in nearby_keywords):
            return value
    return None


def _to_int(raw: str) -> int | None:
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    mapping = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "两": 2}
    if raw in mapping:
        return mapping[raw]
    if raw.startswith("十") and len(raw) == 2 and raw[1] in mapping:
        return 10 + mapping[raw[1]]
    if raw.endswith("十") and len(raw) == 2 and raw[0] in mapping:
        return mapping[raw[0]] * 10
    if len(raw) == 3 and raw[1] == "十" and raw[0] in mapping and raw[2] in mapping:
        return mapping[raw[0]] * 10 + mapping[raw[2]]
    return None


def _has_any_keyword(request: str, keywords: list) -> bool:
    return any(keyword in request for keyword in keywords)


def _has_all_keywords(request: str, must_include: list, any_group: list) -> bool:
    return all(keyword in request for keyword in must_include) and any(keyword in request for keyword in any_group)
