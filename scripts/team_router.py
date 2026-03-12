import re


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


def _append_reason(reasons: list, reason: str) -> None:
    if reason and reason not in reasons:
        reasons.append(reason)


def should_use_agent_team(user_request: str) -> dict:
    request = (user_request or "").strip()
    normalized_request = _normalize_request(request)
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
    return {"use_team": True, "reasons": reasons, "execution_profile": execution_profile}


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
        },
        "supervisor_review_fields": [
            "audit_gate",
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
        },
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
            "supervisor_review",
            "render_report",
        ],
    }


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
