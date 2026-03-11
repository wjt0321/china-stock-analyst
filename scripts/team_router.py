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
]


def should_use_agent_team(user_request: str) -> dict:
    request = (user_request or "").strip()
    reasons = []
    stock_codes = re.findall(r"\b[036]\d{5}\b", request)
    if len(set(stock_codes)) >= 2:
        reasons.append("多标的")
    if "多股" in request or "股票池" in request:
        if "多标的" not in reasons:
            reasons.append("多标的")
    if _looks_like_multi_target_by_names(request):
        if "多标的" not in reasons:
            reasons.append("多标的")
    if any(keyword in request for keyword in TEAM_TRIGGER_KEYWORDS):
        reasons.append("验证")
    use_team = bool(reasons)
    return {"use_team": use_team, "reasons": reasons}


def build_skill_chain_plan(use_team: bool) -> dict:
    if use_team:
        return {
            "mode": "agent_team",
            "steps": [
                "collect_data",
                "run_fundamental_expert",
                "run_technical_expert",
                "run_quant_flow_expert",
                "run_risk_expert",
                "run_macro_expert",
                "supervisor_review",
                "render_report",
            ],
        }
    return {
        "mode": "single_flow",
        "steps": [
            "collect_data",
            "run_single_analysis",
            "render_report",
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
