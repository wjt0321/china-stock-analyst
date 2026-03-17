import re
from datetime import datetime, timedelta
from team_router import should_use_agent_team, build_skill_chain_plan
from stock_utils import (
    get_shortline_indicator_recommendations,
    get_realtime_source_pool,
    infer_source_category,
    extract_timestamp_text,
    normalize_timestamp_text,
    validate_stock_code,
    normalize_stock_name,
    is_stock_name_alias,
)


SENTIMENT_MAX_IMPACT = 2.0
EMOTIONAL_NEWS_KEYWORDS = ["暴涨", "暴跌", "惊天", "炸裂", "血赚", "必涨", "必赢", "内幕", "速看"]
LOW_CREDIBILITY_HINTS = ["转载", "自媒体", "论坛", "股吧", "传闻", "小作文", "未证实"]
POSITIVE_SENTIMENT_KEYWORDS = ["利好", "增持", "中标", "回购", "增长", "上调", "突破", "创新高"]
NEGATIVE_SENTIMENT_KEYWORDS = ["利空", "减持", "处罚", "亏损", "下调", "暴雷", "跌停", "终止"]
INDUSTRY_POSITIVE_KEYWORDS = ["景气", "扩产", "提价", "复苏", "高增长", "需求回暖", "高景气"]
INDUSTRY_NEGATIVE_KEYWORDS = ["过剩", "下行", "去库存", "收缩", "需求疲弱", "价格战"]
EVENT_POSITIVE_KEYWORDS = ["中标", "回购", "增持", "政策支持", "订单", "突破"]
EVENT_NEGATIVE_KEYWORDS = ["处罚", "问询", "减持", "终止", "风险提示", "监管关注"]
EXPERT_PRICE_TOLERANCE_RATIO = 0.08
EXPECTED_EXPERT_AGENTS = {
    "industry_researcher": "expert_industry_researcher",
    "event_hunter": "expert_event_hunter",
}
FAILURE_CODE_IDENTITY_CODE_INVALID = "IDENTITY_CODE_INVALID"
FAILURE_CODE_IDENTITY_EVIDENCE_INSUFFICIENT = "IDENTITY_EVIDENCE_INSUFFICIENT"
FAILURE_CODE_IDENTITY_CODE_NAME_MISMATCH = "IDENTITY_CODE_NAME_MISMATCH"
FAILURE_CODE_IDENTITY_NAME_CODE_CONFLICT = "IDENTITY_NAME_CODE_CONFLICT"
FAILURE_CODE_PRICE_CURRENCY_UNIT_INCONSISTENT = "PRICE_CURRENCY_UNIT_INCONSISTENT"
FAILURE_CODE_PRICE_CURRENCY_UNIT_EVIDENCE_INSUFFICIENT = "PRICE_CURRENCY_UNIT_EVIDENCE_INSUFFICIENT"
FAILURE_CODE_PRICE_INVALID = "PRICE_INVALID"
FAILURE_CODE_TRADING_DAY_STALE = "TRADING_DAY_STALE"
FAILURE_REASON_TIPS = {
    "REQUEST_LIMIT_EXCEEDED": "请降低返回条数（建议<=50）后重试。",
    "TIME_RANGE_EXCEEDED": "请缩小时间范围（建议<=180天）后重试。",
    "TARGET_REQUIRED": "请补充股票代码或股票名称后再发起请求。",
    "INTENT_NOT_MATCHED": "未识别到东财意图，已降级为本地分析流程。",
    "DUPLICATE_REQUEST": "请求过于频繁，请稍后重试或补充差异化筛选条件。",
    "SYMBOL_METADATA_UNAVAILABLE": "标的元信息暂不可用，已自动降级为东财/本地流程。",
    FAILURE_CODE_IDENTITY_CODE_INVALID: "请核对股票代码格式（A股6位代码）并重新采样。",
    FAILURE_CODE_IDENTITY_EVIDENCE_INSUFFICIENT: "请补充至少两类可信来源的代码-名称证据。",
    FAILURE_CODE_IDENTITY_CODE_NAME_MISMATCH: "请统一代码与名称映射，移除冲突来源后重试。",
    FAILURE_CODE_IDENTITY_NAME_CODE_CONFLICT: "请确认同名主体对应唯一代码并重新抓取。",
    FAILURE_CODE_PRICE_CURRENCY_UNIT_INCONSISTENT: "请统一价格币种与单位为人民币元/股。",
    FAILURE_CODE_PRICE_CURRENCY_UNIT_EVIDENCE_INSUFFICIENT: "请补充至少两类来源的币种单位证据。",
    FAILURE_CODE_PRICE_INVALID: "请校验价格是否处于 0.1~600.0 元区间。",
    FAILURE_CODE_TRADING_DAY_STALE: "请重采请求交易日内的分钟级行情时间戳。",
}
PRICE_VALID_MIN = 0.1
PRICE_VALID_MAX = 600.0


def parse_search_results_to_report(
    search_results: list,
    stock_code: str,
    stock_name: str = "",
    request_date: str = "",
) -> dict:
    """
    将搜索结果解析为结构化报告数据

    Args:
        search_results: Web Search 返回的结果列表
        stock_code: 股票代码
        stock_name: 股票名称（可选，作为标的绑定锚点）

    Returns:
        包含解析后数据的字典
    """
    report = {
        "stock_code": stock_code,
        "request_date": request_date or "",
        "canonical_code": stock_code,
        "canonical_name": normalize_stock_name(stock_name) if stock_name else "",
        "price_info": {},
        "fund_flow": {},
        "financial": {},
        "shortline_signals": {},
        "news": [],
        "field_sources": {},
        "identity_mentions": [],
        "price_semantic_records": [],
        "audit_gate": {
            "passed": True,
            "require_resample": False,
            "failed_fields": [],
            "downgrade_reasons": [],
            "next_action": "continue",
        },
        "expert_outputs": {},
        "expert_identity_gate": {
            "passed": True,
            "identity_passed": True,
            "price_passed": True,
            "require_block": False,
            "failed_agents": [],
            "failed_reasons": [],
            "next_action": "continue",
        },
        "process_block": {
            "blocked": False,
            "blocked_stage": "",
            "reason": "",
            "next_action": "continue",
        },
        "supervisor_review": {},
    }

    for result in search_results:
        title = result.get('title', '')
        snippet = result.get('snippet', '')
        link = result.get('link', '')
        source = _build_source_meta(result)
        report["identity_mentions"].extend(_extract_identity_mentions(f"{title} {snippet}", source))
        price_semantic = _extract_price_semantic(
            f"{title} {snippet}",
            source,
            request_date=request_date,
        )
        if price_semantic:
            report["price_semantic_records"].append(price_semantic)

        # 解析价格信息
        if '最新价' in snippet or '股价' in title:
            parsed = _parse_price(snippet, request_date=request_date)
            report['price_info'].update(parsed)
            _record_field_sources(report, "price", parsed, source)

        # 解析资金流向
        if '资金流向' in title or '主力' in snippet:
            parsed = _parse_fund_flow(snippet)
            report['fund_flow'].update(parsed)
            _record_field_sources(report, "fund_flow", parsed, source)

        if (
            '净利润' in snippet or '业绩' in title or '预增' in snippet
            or '营业收入' in snippet or '同比' in snippet or '环比' in snippet
        ):
            parsed = _parse_financial(snippet)
            report['financial'].update(parsed)
            _record_field_sources(report, "financial", parsed, source)
        if _contains_shortline_indicator(snippet, title):
            _parse_shortline_signals(snippet, report)

        # 保存新闻
        report['news'].append({
            'title': title,
            'snippet': snippet[:150],
            'link': link,
            'timestamp': source.get("timestamp", "N/A"),
            'source_category': source.get("source_category", "其他来源"),
        })
    report["audit_gate"] = _run_data_authenticity_audit(report, request_date=request_date)
    _apply_audit_downgrade(report)
    report["sentiment_governance"] = _govern_news_sentiment(report.get("news", []))
    industry_output = _build_industry_research_output(report)
    event_output = _build_event_hunter_output(report)
    report["expert_outputs"]["industry_researcher"] = industry_output
    report["expert_outputs"]["event_hunter"] = event_output
    identity_gate = _run_expert_identity_gate(report)
    report["expert_identity_gate"] = identity_gate
    report["repair_suggestions"] = identity_gate.get("repair_suggestions", [])
    report["authenticity_verification"] = identity_gate.get("authenticity_summary", {})
    if identity_gate.get("require_block"):
        report["process_block"] = _build_process_block(identity_gate)
        report["supervisor_review"] = _build_blocked_supervisor_review(identity_gate)
    else:
        report["supervisor_review"] = _run_supervisor_review(report, industry_output, event_output)
    report["evidences"] = _merge_all_evidences(report)

    return report


# 优先从明确的价格关键词后提取股价，避免误取止损位/历史价等
_PRICE_ANCHOR_RE = re.compile(
    r'(?P<label>最新价|现价|收盘价|当前价格|报价|今日收盘|当日收盘|股价)\s*[：:=]?\s*'
    r'(?P<value>[0-9]+\.?[0-9]*)\s*元'
)
_PRICE_FALLBACK_RE = re.compile(r'([0-9]+\.?[0-9]*)\s*元(?:/股)?')
# A股合理价格区间（单位：元/股）
_A_SHARE_PRICE_MIN = 0.1
_A_SHARE_PRICE_MAX = 600.0


def _parse_price(snippet: str, request_date: str = "") -> dict:
    parsed = {}
    same_day_close = _is_same_day_close_semantic(snippet, request_date=request_date)
    # 优先：从语义锚点（最新价/现价等）后取价格
    anchor_matched = False
    for m in _PRICE_ANCHOR_RE.finditer(snippet):
        label = (m.group("label") or "").strip()
        if label == "收盘价" and not same_day_close:
            continue
        parsed['price'] = m.group("value")
        anchor_matched = True
        break
    if not anchor_matched and ("收盘价" not in snippet or same_day_close):
        # 降级：遍历所有"X元"，取第一个落在A股合理价格区间的值
        for m2 in _PRICE_FALLBACK_RE.finditer(snippet):
            try:
                val = float(m2.group(1))
                if _A_SHARE_PRICE_MIN <= val <= _A_SHARE_PRICE_MAX:
                    parsed['price'] = m2.group(1)
                    break
            except ValueError:
                continue

    # 匹配涨跌幅
    change_match = re.search(r'([+-]?\d+\.?\d*)\s*%', snippet)
    if change_match:
        parsed['change'] = change_match.group(1)
    turnover_match = re.search(r'成交额[^0-9]*([0-9]+\.?[0-9]*)\s*(亿元|亿|万元|万|元)', snippet)
    if turnover_match:
        turnover = _normalize_to_wan(float(turnover_match.group(1)), turnover_match.group(2))
        parsed['turnover'] = f"{turnover:.2f}"
    return parsed


def _parse_fund_flow(snippet: str) -> dict:
    parsed = {}
    main = _extract_flow_amount(snippet, '主力')
    if main is not None:
        parsed['main'] = f"{main:.2f}"
    retail = _extract_flow_amount(snippet, '散户')
    if retail is not None:
        parsed['retail'] = f"{retail:.2f}"
    return parsed


# 资金流向方向关键词（正向=流入，负向=流出）
_FLOW_INFLOW_WORDS = ["净流入", "净买入", "主动买入", "买超"]
_FLOW_OUTFLOW_WORDS = ["净流出", "净卖出", "主动卖出", "卖超"]
_FLOW_INFLOW_HINTS = _FLOW_INFLOW_WORDS + ["流入", "买入"]
_FLOW_OUTFLOW_HINTS = _FLOW_OUTFLOW_WORDS + ["流出", "卖出"]
# 同义方向词结合体，直接嵌入正则
_FLOW_DIRECTION_GROUP = r'(' + '|'.join(_FLOW_OUTFLOW_WORDS + _FLOW_INFLOW_WORDS) + r')'


def _extract_flow_amount(snippet: str, role: str):
    # 优先：在角色关键词后直接捕获方向词+数字（防止跨角色方向污染）
    pattern_with_dir = (
        rf'{role}[资金]*[^\uff0c\u3002,\uff1b;]{{0,20}}?'
        rf'{_FLOW_DIRECTION_GROUP}\s*'
        rf'([+-]?\d+\.?\d*)\s*(\u4ebf\u5143|\u4ebf|\u4e07\u5143|\u4e07|\u5143)?'
    )
    match = re.search(pattern_with_dir, snippet)
    if match:
        direction = match.group(1)
        amount_raw = float(match.group(2))
        unit = match.group(3) or '\u4e07\u5143'
        amount = _normalize_to_wan(amount_raw, unit)
        if direction in _FLOW_OUTFLOW_WORDS:
            return -abs(amount)
        return abs(amount)

    # 降级：无方向词时，仅在角色关键词后5字符内找数字，防止跨描述污染
    pattern_no_dir = rf'({role}[资金]*[^\uff0c\u3002,\uff1b;]{{0,30}}?)([+-]?\d+\.?\d*)\s*(\u4ebf\u5143|\u4ebf|\u4e07\u5143|\u4e07|\u5143)?'
    match2 = re.search(pattern_no_dir, snippet)
    if not match2:
        return None
    context_text = match2.group(1) or ""
    amount_raw = float(match2.group(2))
    unit = match2.group(3) or '\u4e07\u5143'
    amount = _normalize_to_wan(abs(amount_raw), unit)
    if amount_raw < 0:
        return -amount
    if any(word in context_text for word in _FLOW_OUTFLOW_HINTS):
        return -amount
    if any(word in context_text for word in _FLOW_INFLOW_HINTS):
        return amount
    return None


def _normalize_to_wan(value: float, unit: str) -> float:
    if unit in ('亿元', '亿'):
        return value * 10000
    if unit in ('元',):
        return value / 10000
    return value


def _parse_financial(snippet: str) -> dict:
    parsed = {'news': snippet[:200]}
    revenue_match = re.search(r'营业收入[^0-9]*([0-9]+\.?[0-9]*)\s*(亿元|亿|万元|万|元)', snippet)
    if revenue_match:
        parsed['revenue'] = f"{float(revenue_match.group(1)):.2f}"
        parsed['revenue_unit'] = revenue_match.group(2)
    yoy_match = re.search(r'同比(?:增长|下降)?\s*([+-]?[0-9]+\.?[0-9]*)\s*%', snippet)
    if yoy_match:
        parsed['yoy'] = f"{float(yoy_match.group(1)):.2f}"
    qoq_match = re.search(r'环比(?:增长|下降)?\s*([+-]?[0-9]+\.?[0-9]*)\s*%', snippet)
    if qoq_match:
        parsed['qoq'] = f"{float(qoq_match.group(1)):.2f}"
    # 优先从 snippet 提取财报期（避免用今天覆盖财报实际报告期）
    as_of_extracted = _extract_financial_report_date(snippet)
    if as_of_extracted:
        parsed['as_of'] = as_of_extracted
        parsed['as_of_source'] = 'extracted'
    else:
        parsed['as_of'] = datetime.now().strftime('%Y-%m-%d')
        parsed['as_of_source'] = 'fallback_today'  # 无法从文本确认报告期，以当日作为兜底
    return parsed


def _extract_financial_report_date(snippet: str) -> str:
    """从财务文本中提取报告期日期，支持季报/年报/半年报/Qx 格式"""
    # 格式1：2025年三季报、2024年年报
    m = re.search(r'(20\d{2})年(一季报|半年报|三季报|年报|一季度|二季度|三季度|四季度)', snippet)
    if m:
        year = int(m.group(1))
        period = m.group(2)
        period_date_map = {
            '一季报': f'{year}-03-31', '一季度': f'{year}-03-31',
            '半年报': f'{year}-06-30', '二季度': f'{year}-06-30',
            '三季报': f'{year}-09-30', '三季度': f'{year}-09-30',
            '年报':   f'{year}-12-31', '四季度': f'{year}-12-31',
        }
        return period_date_map.get(period, '')
    # 格式2：2024Q1、2024Q4
    m2 = re.search(r'(20\d{2})[年\-]?[Qq]([1-4])', snippet)
    if m2:
        year, quarter = int(m2.group(1)), int(m2.group(2))
        q_end = {1: '03-31', 2: '06-30', 3: '09-30', 4: '12-31'}
        return f'{year}-{q_end[quarter]}'
    # 格式3：2025-03-31 或 2025年03月31日
    m3 = re.search(r'(20\d{2})[-年](\d{1,2})[-月](\d{1,2})', snippet)
    if m3:
        return f'{m3.group(1)}-{int(m3.group(2)):02d}-{int(m3.group(3)):02d}'
    return ''


def _contains_shortline_indicator(snippet: str, title: str) -> bool:
    text = f"{title} {snippet}"
    keywords = ["VWAP", "量比", "ATR", "止损", "偏离"]
    return any(keyword in text for keyword in keywords)


def _parse_shortline_signals(snippet: str, report: dict):
    signals = report.setdefault("shortline_signals", {})
    vwap_match = re.search(r'VWAP[^0-9\-+]*([+-]?[0-9]+\.?[0-9]*)\s*%', snippet, re.IGNORECASE)
    if vwap_match:
        signals["vwap_deviation"] = f"{float(vwap_match.group(1)):.2f}"
    volume_ratio_match = re.search(r'量比[^0-9]*([0-9]+\.?[0-9]*)', snippet)
    if volume_ratio_match:
        signals["volume_ratio"] = f"{float(volume_ratio_match.group(1)):.2f}"
    atr_stop_match = re.search(r'(?:建议)?止损[^0-9]*([0-9]+\.?[0-9]*)\s*元', snippet)
    if atr_stop_match:
        signals["atr_stop"] = f"{float(atr_stop_match.group(1)):.2f}"
    atr_value_match = re.search(r'ATR(?:14)?[^0-9]*([0-9]+\.?[0-9]*)', snippet, re.IGNORECASE)
    if atr_value_match:
        signals["atr_value"] = f"{float(atr_value_match.group(1)):.2f}"
    price_val = _safe_float(report.get("price_info", {}).get("price"))
    atr_val = _safe_float(signals.get("atr_value"))
    if signals.get("atr_stop") in (None, "", "N/A") and price_val > 0 and atr_val > 0:
        signals["atr_stop"] = f"{max(price_val - 1.5 * atr_val, 0):.2f}"


def _build_source_meta(result: dict) -> dict:
    title = result.get("title", "")
    snippet = result.get("snippet", "")
    link = result.get("link", "")
    raw_timestamp = (
        result.get("timestamp")
        or result.get("published_at")
        or extract_timestamp_text(f"{title} {snippet}", "")
    )
    normalized_timestamp = normalize_timestamp_text(raw_timestamp)
    if not normalized_timestamp:
        normalized_timestamp = "N/A"
    return {
        "source_url": link or "N/A",
        "source_title": title or "N/A",
        "source_category": infer_source_category(link, title),
        "timestamp": normalized_timestamp,
    }


def _record_field_sources(report: dict, section: str, updates: dict, source: dict):
    if not updates:
        return
    field_sources = report.setdefault("field_sources", {})
    for key, value in updates.items():
        if str(value).strip() in ("", "N/A", "未知"):
            continue
        field = f"{section}.{key}"
        records = field_sources.setdefault(field, [])
        records.append(
            {
                "value": str(value),
                "source_url": source.get("source_url", "N/A"),
                "source_title": source.get("source_title", "N/A"),
                "source_category": source.get("source_category", "其他来源"),
                "timestamp": source.get("timestamp", "N/A"),
            }
        )


# 代码与名称关联的局部窗口大小（字符数），避免跨标的张冠李戴
_IDENTITY_WINDOW_SIZE = 40
_IDENTITY_MAX_BIND_GAP = 6
_IDENTITY_NAME_CHARS = r"[\u4e00-\u9fa5A-Za-z\*STＳＴ]"
_IDENTITY_AMBIGUOUS_SEPARATORS_RE = re.compile(r"(与|和|及|或|对比|vs|VS|/|、)")
_IDENTITY_NOISE_KEYWORDS = [
    "最新价", "行情", "播报", "快讯", "报价", "更新", "盘中", "交易", "数据", "资讯",
    "行业", "竞争", "格局", "需求", "回暖", "监管", "问询", "风险", "公告", "事件", "冲击", "趋势",
]


def _extract_identity_mentions(text: str, source: dict) -> list:
    mentions = []
    merged_text = text or ""
    for match in re.finditer(r"(?<!\d)([036]\d{5})(?!\d)", merged_text):
        code = match.group(1)
        candidates = _extract_adjacent_identity_candidates(
            merged_text,
            code,
            match.start(),
            match.end(),
        )
        unique_names = {item["stock_name"] for item in candidates if item.get("stock_name")}
        # 强邻接绑定：同一代码在局部窗口内若出现多个不同名称，视为歧义并拒绝绑定
        if len(unique_names) != 1:
            continue
        best_candidate = sorted(
            candidates,
            key=lambda item: (-item.get("confidence", 0), item.get("distance", 999)),
        )[0]
        mentions.append(
            {
                "stock_code": code,
                "stock_name": best_candidate.get("stock_name", ""),
                "raw_stock_name": best_candidate.get("raw_stock_name", ""),
                "source_url": source.get("source_url", "N/A"),
                "source_title": source.get("source_title", "N/A"),
                "source_category": source.get("source_category", "其他来源"),
                "timestamp": source.get("timestamp", "N/A"),
            }
        )
    unique = []
    seen = set()
    for item in mentions:
        key = (
            item.get("stock_code", ""),
            item.get("stock_name", ""),
            item.get("source_url", ""),
            item.get("timestamp", ""),
        )
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _extract_adjacent_identity_candidates(text: str, stock_code: str, code_start: int, code_end: int) -> list:
    if not text:
        return []
    local_start = max(0, code_start - _IDENTITY_WINDOW_SIZE)
    local_end = min(len(text), code_end + _IDENTITY_WINDOW_SIZE)
    local_text = text[local_start:local_end]
    local_code_start = code_start - local_start
    local_code_end = code_end - local_start
    patterns = [
        # 名称(代码)
        (re.compile(rf"({_IDENTITY_NAME_CHARS}{{2,20}})\s*[\(（]\s*{stock_code}\s*[\)）]"), "name_before_code", 3),
        # 名称 代码
        (re.compile(rf"({_IDENTITY_NAME_CHARS}{{2,20}})\s*{stock_code}"), "name_before_code", 2),
        # 代码:名称
        (re.compile(rf"{stock_code}\s*[-—:：]?\s*({_IDENTITY_NAME_CHARS}{{2,20}})"), "code_before_name", 2),
    ]
    candidates = []
    for pattern, bind_type, confidence in patterns:
        for matched in pattern.finditer(local_text):
            if not (matched.start() <= local_code_start <= matched.end()):
                continue
            raw_name = matched.group(1)
            normalized_name = _normalize_identity_name_candidate(raw_name)
            if not normalized_name:
                continue
            if bind_type == "name_before_code":
                between = local_text[matched.end(1):local_code_start]
                distance = max(local_code_start - matched.end(1), 0)
            else:
                between = local_text[local_code_end:matched.start(1)]
                distance = max(matched.start(1) - local_code_end, 0)
            if distance > _IDENTITY_MAX_BIND_GAP:
                continue
            if _IDENTITY_AMBIGUOUS_SEPARATORS_RE.search(between or ""):
                continue
            candidates.append(
                {
                    "stock_name": normalized_name,
                    "raw_stock_name": raw_name,
                    "distance": distance,
                    "confidence": confidence,
                }
            )
    deduped = []
    seen = set()
    for item in candidates:
        key = (item.get("stock_name", ""), item.get("raw_stock_name", ""), item.get("distance", 0))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _normalize_identity_name_candidate(raw_name: str) -> str:
    cleaned = re.sub(r"^(股票|个股|代码|标的)", "", raw_name or "").strip(" -—:：，,。.;；")
    if not cleaned or not re.search(r"[\u4e00-\u9fa5A-Za-z]", cleaned):
        return ""
    if any(keyword in cleaned for keyword in _IDENTITY_NOISE_KEYWORDS):
        return ""
    return normalize_stock_name(cleaned)


def _extract_stock_name_candidates(text: str, stock_code: str) -> list:
    candidates = []
    noise_keywords = [
        "最新价", "行情", "播报", "快讯", "报价", "更新", "盘中", "交易", "数据", "资讯",
        "行业", "竞争", "格局", "需求", "回暖", "监管", "问询", "风险", "公告", "事件", "冲击", "趋势",
    ]
    patterns = [
        rf"([\u4e00-\u9fa5A-Za-z\*STＳＴ]{{2,20}})\s*[\(（]?{stock_code}[\)）]?",
        rf"{stock_code}\s*[-—:：]?\s*([\u4e00-\u9fa5A-Za-z\*STＳＴ]{{2,20}})",
        rf"([\u4e00-\u9fa5A-Za-z\*STＳＴ]{{2,20}})\s*\(\s*{stock_code}\s*\)",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text or ""):
            cleaned = re.sub(r"^(股票|个股|代码|标的)", "", match).strip(" -—:：，,。.;；")
            if cleaned and re.search(r"[\u4e00-\u9fa5A-Za-z]", cleaned):
                if any(keyword in cleaned for keyword in noise_keywords):
                    continue
                candidates.append(cleaned)
    unique = []
    seen = set()
    for item in candidates:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _extract_price_semantic(text: str, source: dict, request_date: str = "") -> dict:
    merged_text = text or ""
    if not re.search(r"(最新价|股价|收盘价|现价|报价)", merged_text):
        return {}
    if not _is_same_day_close_semantic(merged_text, request_date=request_date):
        return {}
    currency = "CNY"
    if re.search(r"(美元|USD|美金)", merged_text, re.IGNORECASE):
        currency = "USD"
    elif re.search(r"(港元|HKD)", merged_text, re.IGNORECASE):
        currency = "HKD"
    elif re.search(r"(人民币|CNY|RMB|元)", merged_text, re.IGNORECASE):
        currency = "CNY"
    unit = "元/股"
    if re.search(r"(分/股|分每股|分人民币)", merged_text):
        unit = "分/股"
    elif re.search(r"(港元/股|美元/股|元/股|每股)", merged_text):
        if currency == "USD":
            unit = "美元/股"
        elif currency == "HKD":
            unit = "港元/股"
        else:
            unit = "元/股"
    return {
        "currency": currency,
        "unit": unit,
        "source_url": source.get("source_url", "N/A"),
        "source_title": source.get("source_title", "N/A"),
        "source_category": source.get("source_category", "其他来源"),
        "timestamp": source.get("timestamp", "N/A"),
    }


def _is_same_day_close_semantic(text: str, request_date: str = "") -> bool:
    merged_text = text or ""
    if "收盘价" not in merged_text and "收盘" not in merged_text:
        return True
    if re.search(r"(昨收|昨日收盘|前收|上一交易日收盘|历史收盘|上周收盘|上月收盘)", merged_text):
        return False
    if re.search(r"(今日收盘|当日收盘|本日收盘|今日盘后|当日盘后)", merged_text):
        return True
    request_dt = _parse_day(request_date) or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    explicit_dt = _parse_day(extract_timestamp_text(merged_text, ""))
    if explicit_dt:
        return explicit_dt.date() == request_dt.date()
    # 仅出现“收盘价”但没有“当日/今日”语义和日期锚点，按歧义拒绝处理
    return False


def _run_data_authenticity_audit(report: dict, request_date: str = "") -> dict:
    source_pool = get_realtime_source_pool()
    required_categories = source_pool.get("required_categories", 3)
    threshold_minutes = source_pool.get("timestamp_conflict_threshold_minutes", 90)
    request_dt = _parse_day(request_date) or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    field_sources = report.get("field_sources", {})
    failed_fields = []
    downgrade_reasons = []
    field_results = {}

    for field in source_pool.get("core_fields", []):
        matched_records = _pick_field_records(field_sources, field)
        categories = {item.get("source_category", "其他来源") for item in matched_records}
        parsed_timestamps = [_parse_timestamp(item.get("timestamp", "")) for item in matched_records]
        timestamps = [ts for ts in parsed_timestamps if ts]
        timestamp_missing = bool(matched_records) and len(timestamps) < len(matched_records)
        date_rollback = any(ts < request_dt for ts in timestamps)
        timestamp_conflict = _has_timestamp_conflict(timestamps, threshold_minutes)
        category_insufficient = len(categories) < required_categories
        trusted = (
            bool(matched_records)
            and not timestamp_missing
            and not date_rollback
            and not timestamp_conflict
            and not category_insufficient
        )
        consistency = "一致" if trusted else "不一致"
        reasons = []
        if not matched_records:
            reasons.append("缺失来源记录")
        if timestamp_missing:
            reasons.append("缺失时间戳")
        if date_rollback:
            reasons.append("日期回退")
        if timestamp_conflict:
            reasons.append("多源时间戳冲突")
        if category_insufficient:
            reasons.append(f"来源类别不足({len(categories)}/{required_categories})")
        if reasons:
            failed_fields.append(field)
            downgrade_reasons.append(f"{field}: {'、'.join(reasons)}")
        field_results[field] = {
            "trusted": trusted,
            "consistency": consistency,
            "source_count": len(matched_records),
            "category_count": len(categories),
            "records": matched_records,
            "reason": "；".join(reasons) if reasons else "通过",
        }
    passed = len(failed_fields) == 0
    return {
        "passed": passed,
        "require_resample": not passed,
        "failed_fields": failed_fields,
        "downgrade_reasons": downgrade_reasons,
        "next_action": "resample" if not passed else "continue",
        "field_results": field_results,
    }


def _apply_audit_downgrade(report: dict):
    gate = report.get("audit_gate", {})
    if gate.get("passed", True):
        return
    report.setdefault("shortline_signals", {})["audit_downgraded"] = "true"
    report["shortline_signals"]["audit_next_action"] = gate.get("next_action", "resample")


def _pick_field_records(field_sources: dict, simple_field: str) -> list:
    suffix = f".{simple_field}"
    picked = []
    for field_name, records in field_sources.items():
        if field_name.endswith(suffix):
            picked.extend(records)
    return picked


def _has_timestamp_conflict(timestamps: list, threshold_minutes: int) -> bool:
    if len(timestamps) <= 1:
        return False
    min_ts = min(timestamps)
    max_ts = max(timestamps)
    return (max_ts - min_ts) > timedelta(minutes=threshold_minutes)


def _parse_day(day_text: str):
    text = (day_text or "").strip()
    if not text:
        return None
    normalized = normalize_timestamp_text(text)
    return _parse_timestamp(normalized)


def _parse_timestamp(timestamp_text: str):
    text = (timestamp_text or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _govern_news_sentiment(news_items: list) -> dict:
    dedup_seen = set()
    accepted = []
    rejected = []
    deduped_count = 0
    for item in news_items:
        title = (item.get("title", "") or "").strip()
        snippet = (item.get("snippet", "") or "").strip()
        fingerprint = _build_news_fingerprint(title, snippet)
        if fingerprint in dedup_seen:
            deduped_count += 1
            rejected.append(
                {
                    "title": title or "N/A",
                    "reason": "重复内容（标题/摘要高度相似）",
                    "quality_score": 0,
                }
            )
            continue
        dedup_seen.add(fingerprint)
        quality = _score_news_quality(item)
        if quality["accepted"]:
            accepted.append(
                {
                    "title": title or "N/A",
                    "quality_score": quality["score"],
                    "sentiment": _classify_news_sentiment(f"{title} {snippet}"),
                    "reasons": quality["reasons"],
                }
            )
        else:
            rejected.append(
                {
                    "title": title or "N/A",
                    "reason": "；".join(quality["reject_reasons"]) or "质量不达标",
                    "quality_score": quality["score"],
                }
            )
    accepted_count = len(accepted)
    rejected_count = len(rejected)
    total_unique = accepted_count + rejected_count
    avg_quality = (
        sum(item["quality_score"] for item in accepted) / accepted_count if accepted_count else 0.0
    )
    weighted_sentiment_sum = 0.0
    weight_sum = 0.0
    for item in accepted:
        sentiment_val = item["sentiment"]
        quality_weight = item["quality_score"] / 100
        weighted_sentiment_sum += sentiment_val * quality_weight
        weight_sum += quality_weight
    sentiment_score_raw = (weighted_sentiment_sum / weight_sum) if weight_sum else 0.0
    score_adjustment = sentiment_score_raw * (avg_quality / 100) * SENTIMENT_MAX_IMPACT
    if score_adjustment > SENTIMENT_MAX_IMPACT:
        score_adjustment = SENTIMENT_MAX_IMPACT
    if score_adjustment < -SENTIMENT_MAX_IMPACT:
        score_adjustment = -SENTIMENT_MAX_IMPACT
    return {
        "max_impact_cap": f"{SENTIMENT_MAX_IMPACT:.1f}",
        "deduped_count": deduped_count,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "acceptance_ratio": f"{(accepted_count / total_unique * 100):.1f}%" if total_unique else "0.0%",
        "average_quality_score": f"{avg_quality:.1f}",
        "sentiment_score_raw": f"{sentiment_score_raw:.2f}",
        "score_adjustment": f"{score_adjustment:.1f}",
        "accepted_items": accepted,
        "rejected_items": rejected,
    }


def _build_news_fingerprint(title: str, snippet: str) -> str:
    merged = f"{title} {snippet}"
    normalized = re.sub(r"\s+", "", merged.lower())
    normalized = re.sub(r"[^\w\u4e00-\u9fff]", "", normalized)
    return normalized[:80]


def _score_news_quality(news_item: dict) -> dict:
    title = (news_item.get("title", "") or "").strip()
    snippet = (news_item.get("snippet", "") or "").strip()
    link = (news_item.get("link", "") or "").strip().lower()
    source_category = (news_item.get("source_category", "") or "").strip()
    text = f"{title} {snippet}"
    score = 0
    reasons = []
    reject_reasons = []
    if link and link != "n/a":
        score += 25
        reasons.append("包含可追溯链接")
    else:
        reject_reasons.append("缺少来源链接")
    if source_category and source_category != "其他来源":
        score += 20
        reasons.append(f"来源类别可信（{source_category}）")
    else:
        score += 5
        reject_reasons.append("来源类别不明确")
    if re.search(r"(20\d{2}[-/年]\d{1,2}[-/月]\d{1,2}|\d+\.?\d*%|\d+\.?\d*亿|\d+\.?\d*万)", text):
        score += 25
        reasons.append("包含可验证事实数据")
    else:
        reject_reasons.append("缺少可验证事实数据")
    if not any(word in text for word in EMOTIONAL_NEWS_KEYWORDS):
        score += 15
        reasons.append("标题情绪噪声较低")
    else:
        reject_reasons.append("存在情绪化标题词")
    if not any(hint in text for hint in LOW_CREDIBILITY_HINTS):
        score += 15
        reasons.append("未命中低可信传播特征")
    else:
        reject_reasons.append("命中转载/传闻类低可信特征")
    accepted = score >= 60 and len(reject_reasons) <= 2
    return {"score": min(score, 100), "accepted": accepted, "reasons": reasons, "reject_reasons": reject_reasons}


def _classify_news_sentiment(text: str) -> int:
    positive_hits = sum(1 for word in POSITIVE_SENTIMENT_KEYWORDS if word in text)
    negative_hits = sum(1 for word in NEGATIVE_SENTIMENT_KEYWORDS if word in text)
    if positive_hits > negative_hits:
        return 1
    if negative_hits > positive_hits:
        return -1
    return 0


def _build_industry_research_output(report: dict) -> dict:
    news_items = report.get("news", [])
    stock_code = report.get("stock_code", "")
    anchor_price = report.get("price_info", {}).get("price", "N/A")
    positive_hits = 0
    negative_hits = 0
    evidences = []
    for item in news_items:
        text = f"{item.get('title', '')} {item.get('snippet', '')}"
        pos = sum(1 for kw in INDUSTRY_POSITIVE_KEYWORDS if kw in text)
        neg = sum(1 for kw in INDUSTRY_NEGATIVE_KEYWORDS if kw in text)
        positive_hits += pos
        negative_hits += neg
        if pos > 0 or neg > 0:
            evidences.append(
                {
                    "conclusion": "行业景气证据",
                    "value": item.get("title", "N/A"),
                    "source_url": item.get("link", "N/A"),
                    "timestamp": item.get("timestamp", "N/A"),
                }
            )
    score = 50 + positive_hits * 8 - negative_hits * 8
    score = max(0, min(score, 100))
    if score >= 65:
        outlook = "景气上行"
        decision_hint = "可做"
    elif score <= 40:
        outlook = "景气承压"
        decision_hint = "回避"
    else:
        outlook = "景气中性"
        decision_hint = "观察"
    inflection = "上行拐点待确认"
    if positive_hits - negative_hits >= 2:
        inflection = "上行拐点初现"
    elif negative_hits - positive_hits >= 2:
        inflection = "下行拐点风险增加"
    return {
        "agent": "expert_industry_researcher",
        "stock_code": stock_code,
        "as_of_price": str(anchor_price),
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "score": score,
        "outlook": outlook,
        "inflection": inflection,
        "competition_landscape": "头部集中度与议价能力仍需持续跟踪",
        "drivers": ["景气词命中统计", "供需节奏", "竞争格局变化"],
        "risk_hint": "若行业新闻转向负面且持续两日以上，需下调仓位",
        "decision_hint": decision_hint,
        "evidences": evidences[:5],
    }


def _build_event_hunter_output(report: dict) -> dict:
    news_items = report.get("news", [])
    stock_code = report.get("stock_code", "")
    anchor_price = report.get("price_info", {}).get("price", "N/A")
    positive_hits = 0
    negative_hits = 0
    regulation_hits = 0
    evidences = []
    for item in news_items:
        text = f"{item.get('title', '')} {item.get('snippet', '')}"
        pos = sum(1 for kw in EVENT_POSITIVE_KEYWORDS if kw in text)
        neg = sum(1 for kw in EVENT_NEGATIVE_KEYWORDS if kw in text)
        positive_hits += pos
        negative_hits += neg
        if any(kw in text for kw in ["监管", "问询", "处罚", "异动公告"]):
            regulation_hits += 1
        if pos > 0 or neg > 0:
            impact = "正向" if pos >= neg else "负向"
            evidences.append(
                {
                    "conclusion": f"事件冲击{impact}",
                    "value": item.get("title", "N/A"),
                    "source_url": item.get("link", "N/A"),
                    "timestamp": item.get("timestamp", "N/A"),
                }
            )
    score = 50 + positive_hits * 10 - negative_hits * 12
    score = max(0, min(score, 100))
    if score >= 65:
        impact_direction = "正向"
        decision_hint = "可做"
    elif score <= 40:
        impact_direction = "负向"
        decision_hint = "回避"
    else:
        impact_direction = "中性"
        decision_hint = "观察"
    strength = "弱"
    if abs(positive_hits - negative_hits) >= 3:
        strength = "强"
    elif abs(positive_hits - negative_hits) >= 1:
        strength = "中"
    return {
        "agent": "expert_event_hunter",
        "stock_code": stock_code,
        "as_of_price": str(anchor_price),
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "score": score,
        "impact_direction": impact_direction,
        "impact_strength": strength,
        "time_window": "1-3个交易日",
        "regulatory_signal": "高" if regulation_hits >= 2 else "中" if regulation_hits == 1 else "低",
        "action_hint": "事件窗口内缩短复核周期，优先跟踪公告原文",
        "decision_hint": decision_hint,
        "evidences": evidences[:5],
    }


def _validate_identity_with_sources(report: dict, expected_code: str) -> dict:
    mentions = report.get("identity_mentions", [])
    matched = [item for item in mentions if item.get("stock_code") == expected_code]
    categories = {item.get("source_category", "其他来源") for item in matched}
    reasons = []
    reason_codes = []
    if len(categories) < 2:
        reasons.append(f"身份来源类别不足({len(categories)}/2)")
        reason_codes.append(FAILURE_CODE_IDENTITY_EVIDENCE_INSUFFICIENT)
    canonical_code = report.get("canonical_code", expected_code) or expected_code
    canonical_name = normalize_stock_name(report.get("canonical_name", ""))
    canonical_candidates = []
    for item in matched:
        normalized = normalize_stock_name(item.get("stock_name", ""))
        if normalized:
            canonical_candidates.append(normalized)
    canonical_candidates = list(dict.fromkeys(canonical_candidates))
    if canonical_name:
        for candidate in canonical_candidates:
            if not is_stock_name_alias(canonical_name, candidate):
                reasons.append(f"代码{expected_code}对应名称冲突: {canonical_name} vs {candidate}")
                reason_codes.append(FAILURE_CODE_IDENTITY_CODE_NAME_MISMATCH)
                break
    elif canonical_candidates:
        canonical_name = canonical_candidates[0]
        for candidate in canonical_candidates[1:]:
            if not is_stock_name_alias(canonical_name, candidate):
                reasons.append(f"代码{expected_code}对应名称冲突: {canonical_name} vs {candidate}")
                reason_codes.append(FAILURE_CODE_IDENTITY_CODE_NAME_MISMATCH)
                break
    else:
        reasons.append(f"未提取到代码{expected_code}对应名称")
        reason_codes.append(FAILURE_CODE_IDENTITY_EVIDENCE_INSUFFICIENT)
    conflicting_mentions = []
    if canonical_name:
        for item in mentions:
            item_name = item.get("stock_name", "")
            if not is_stock_name_alias(item_name, canonical_name):
                continue
            if item.get("stock_code") != expected_code:
                conflicting_mentions.append(item)
        if conflicting_mentions:
            conflict_codes = sorted({item.get("stock_code", "") for item in conflicting_mentions if item.get("stock_code")})
            reasons.append(f"名称{canonical_name}映射到多个代码: {expected_code} vs {','.join(conflict_codes)}")
            reason_codes.append(FAILURE_CODE_IDENTITY_NAME_CODE_CONFLICT)
    evidences = []
    for item in matched[:6]:
        evidences.append(
            {
                "conclusion": "身份映射证据",
                "value": f"{item.get('stock_name', 'N/A')}({item.get('stock_code', 'N/A')})",
                "source_url": item.get("source_url", "N/A"),
                "timestamp": item.get("timestamp", "N/A"),
                "source_category": item.get("source_category", "其他来源"),
            }
        )
    return {
        "passed": len(reasons) == 0,
        "reasons": reasons,
        "reason_codes": list(dict.fromkeys(reason_codes)),
        "evidences": evidences,
        "summary": {
            "canonical_code": canonical_code or "N/A",
            "canonical_name": canonical_name or "N/A",
            "evidence_count": len(matched),
            "category_count": len(categories),
        },
    }


def _validate_price_semantics(report: dict) -> dict:
    records = report.get("price_semantic_records", [])
    if not records:
        return {
            "passed": True,
            "reasons": [],
            "reason_codes": [],
            "evidences": [],
            "summary": {"currency": "N/A", "unit": "N/A", "category_count": 0},
        }
    categories = {item.get("source_category", "其他来源") for item in records}
    reasons = []
    reason_codes = []
    if len(categories) < 2:
        reasons.append(f"币种单位来源类别不足({len(categories)}/2)")
        reason_codes.append(FAILURE_CODE_PRICE_CURRENCY_UNIT_EVIDENCE_INSUFFICIENT)
    currencies = {item.get("currency", "N/A") for item in records}
    units = {item.get("unit", "N/A") for item in records}
    if len(currencies) > 1 or len(units) > 1:
        reasons.append(f"币种或单位不一致: currency={','.join(sorted(currencies))}; unit={','.join(sorted(units))}")
        reason_codes.append(FAILURE_CODE_PRICE_CURRENCY_UNIT_INCONSISTENT)
    currency = next(iter(currencies)) if currencies else "N/A"
    unit = next(iter(units)) if units else "N/A"
    evidences = []
    for item in records[:6]:
        evidences.append(
            {
                "conclusion": "价格币种单位证据",
                "value": f"{item.get('currency', 'N/A')} {item.get('unit', 'N/A')}",
                "source_url": item.get("source_url", "N/A"),
                "timestamp": item.get("timestamp", "N/A"),
                "source_category": item.get("source_category", "其他来源"),
            }
        )
    return {
        "passed": len(reasons) == 0,
        "reasons": reasons,
        "reason_codes": list(dict.fromkeys(reason_codes)),
        "evidences": evidences,
        "summary": {
            "currency": currency,
            "unit": unit,
            "category_count": len(categories),
            "record_count": len(records),
        },
    }


def _validate_price_validity(report: dict) -> dict:
    price_text = report.get("price_info", {}).get("price", "")
    price_value = _safe_float(price_text)
    reasons = []
    reason_codes = []
    if price_value <= 0:
        reasons.append("缺失可用价格锚点")
        reason_codes.append(FAILURE_CODE_PRICE_INVALID)
    elif price_value < PRICE_VALID_MIN or price_value > PRICE_VALID_MAX:
        reasons.append(
            f"价格超出A股有效区间({PRICE_VALID_MIN:.1f}~{PRICE_VALID_MAX:.1f}元): {price_value:.2f}"
        )
        reason_codes.append(FAILURE_CODE_PRICE_INVALID)
    evidences = []
    for item in _pick_field_records(report.get("field_sources", {}), "price")[:3]:
        evidences.append(
            {
                "conclusion": "价格有效性证据",
                "value": item.get("value", "N/A"),
                "source_url": item.get("source_url", "N/A"),
                "timestamp": item.get("timestamp", "N/A"),
                "source_category": item.get("source_category", "其他来源"),
            }
        )
    return {
        "passed": len(reason_codes) == 0,
        "reasons": reasons,
        "reason_codes": list(dict.fromkeys(reason_codes)),
        "evidences": evidences,
        "summary": {
            "price": f"{price_value:.2f}" if price_value > 0 else "N/A",
            "valid_range": f"{PRICE_VALID_MIN:.1f}-{PRICE_VALID_MAX:.1f}",
        },
    }


def _validate_trading_day_timeliness(report: dict, request_date: str = "") -> dict:
    strict_mode = bool(str(request_date or "").strip())
    request_dt = _parse_day(request_date) or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    timestamps = _collect_timestamps_for_timeliness(report)
    reasons = []
    reason_codes = []
    evidences = []
    for ts in sorted(timestamps, reverse=True)[:6]:
        evidences.append(
            {
                "conclusion": "交易日时效证据",
                "value": ts.strftime("%Y-%m-%d %H:%M"),
                "source_url": "N/A",
                "timestamp": ts.strftime("%Y-%m-%d %H:%M"),
                "source_category": "时效校验",
            }
        )
    if not strict_mode:
        latest_value = max(timestamps).strftime("%Y-%m-%d %H:%M") if timestamps else "N/A"
        return {
            "passed": True,
            "reasons": [],
            "reason_codes": [],
            "evidences": evidences,
            "summary": {
                "request_date": "N/A",
                "latest_timestamp": latest_value,
                "strict_mode": "off",
            },
        }
    if not timestamps:
        reasons.append("缺失可用于交易日时效校验的时间戳")
        reason_codes.append(FAILURE_CODE_TRADING_DAY_STALE)
    else:
        latest_ts = max(timestamps)
        if _is_trading_weekday(request_dt):
            if latest_ts.date() != request_dt.date():
                reasons.append(
                    f"交易日时效不通过: 最新时间戳{latest_ts.strftime('%Y-%m-%d %H:%M')} 非请求交易日{request_dt.strftime('%Y-%m-%d')}"
                )
                reason_codes.append(FAILURE_CODE_TRADING_DAY_STALE)
        else:
            previous_trade_day = _previous_trading_day(request_dt)
            if latest_ts.date() < previous_trade_day.date():
                reasons.append(
                    f"交易日时效不通过: 最新时间戳{latest_ts.strftime('%Y-%m-%d %H:%M')} 早于最近交易日{previous_trade_day.strftime('%Y-%m-%d')}"
                )
                reason_codes.append(FAILURE_CODE_TRADING_DAY_STALE)
    latest_value = max(timestamps).strftime("%Y-%m-%d %H:%M") if timestamps else "N/A"
    return {
        "passed": len(reason_codes) == 0,
        "reasons": reasons,
        "reason_codes": list(dict.fromkeys(reason_codes)),
        "evidences": evidences,
        "summary": {
            "request_date": request_dt.strftime("%Y-%m-%d"),
            "latest_timestamp": latest_value,
            "strict_mode": "on",
        },
    }


def _collect_timestamps_for_timeliness(report: dict) -> list:
    timestamps = []
    for section in ("identity_mentions", "price_semantic_records"):
        for item in report.get(section, []):
            parsed = _parse_timestamp(item.get("timestamp", ""))
            if parsed:
                timestamps.append(parsed)
    for record in _pick_field_records(report.get("field_sources", {}), "price"):
        parsed = _parse_timestamp(record.get("timestamp", ""))
        if parsed:
            timestamps.append(parsed)
    unique = []
    seen = set()
    for item in timestamps:
        key = item.strftime("%Y-%m-%d %H:%M")
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _is_trading_weekday(target_dt: datetime) -> bool:
    return target_dt.weekday() < 5


def _previous_trading_day(target_dt: datetime) -> datetime:
    cursor = target_dt
    while True:
        cursor = cursor - timedelta(days=1)
        if _is_trading_weekday(cursor):
            return cursor


def _build_repair_suggestions(failed_reason_codes: list, stock_code: str = "", canonical_name: str = "") -> list:
    suggestions = []
    seen = set()
    identity_codes = {
        FAILURE_CODE_IDENTITY_CODE_INVALID,
        FAILURE_CODE_IDENTITY_EVIDENCE_INSUFFICIENT,
        FAILURE_CODE_IDENTITY_CODE_NAME_MISMATCH,
        FAILURE_CODE_IDENTITY_NAME_CODE_CONFLICT,
    }
    price_codes = {
        FAILURE_CODE_PRICE_INVALID,
        FAILURE_CODE_PRICE_CURRENCY_UNIT_INCONSISTENT,
        FAILURE_CODE_PRICE_CURRENCY_UNIT_EVIDENCE_INSUFFICIENT,
    }
    for code in failed_reason_codes:
        if code in seen:
            continue
        seen.add(code)
        if code in identity_codes:
            suggestions.append(
                {
                    "failure_code": code,
                    "category": "code_name_consistency",
                    "problem": "代码与名称映射不一致或证据不足",
                    "required_action": "补充2类以上可信来源并统一代码名称映射",
                    "steps": [
                        f"固定标的锚点为 {stock_code or 'N/A'} / {normalize_stock_name(canonical_name) or 'N/A'}",
                        "仅保留名称-代码强邻接证据（如 名称(代码)）",
                        "移除跨标的混写与歧义文本后重新采样",
                    ],
                    "blocking": True,
                }
            )
            continue
        if code in price_codes:
            suggestions.append(
                {
                    "failure_code": code,
                    "category": "price_validity",
                    "problem": "价格锚点无效或币种/单位口径不一致",
                    "required_action": "统一价格口径为CNY元/股并校验价格区间",
                    "steps": [
                        "优先采集交易所或主流行情终端的当日最新价",
                        "将币种统一到人民币，单位统一到元/股",
                        f"校验价格在有效区间 {PRICE_VALID_MIN:.1f}~{PRICE_VALID_MAX:.1f} 元后再进入专家分析",
                    ],
                    "blocking": True,
                }
            )
            continue
        if code == FAILURE_CODE_TRADING_DAY_STALE:
            suggestions.append(
                {
                    "failure_code": code,
                    "category": "trading_day_timeliness",
                    "problem": "关键行情时间戳不在请求交易日窗口内",
                    "required_action": "重采样当日交易时段数据并补齐分钟级时间戳",
                    "steps": [
                        "按请求日期重新抓取交易时段内行情快照",
                        "确保至少一条价格证据含 YYYY-MM-DD HH:MM 时间戳",
                        "复核最新时间戳与请求交易日一致后再继续",
                    ],
                    "blocking": True,
                }
            )
    return suggestions


def _run_expert_identity_gate(report: dict) -> dict:
    stock_code = report.get("stock_code", "")
    canonical_price = _safe_float(report.get("price_info", {}).get("price"))
    expected_agents = EXPECTED_EXPERT_AGENTS
    failed_agents = []
    failed_reasons = []
    failed_reason_codes = []
    request_date = report.get("request_date", "")
    identity_passed = validate_stock_code(stock_code)
    price_passed = canonical_price > 0
    trading_day_passed = True
    if not identity_passed:
        failed_reasons.append(f"stock_code非法: {stock_code or 'N/A'}")
        failed_reason_codes.append(FAILURE_CODE_IDENTITY_CODE_INVALID)
    identity_source_result = _validate_identity_with_sources(report, stock_code)
    if not identity_source_result.get("passed", True):
        identity_passed = False
        failed_reasons.extend(identity_source_result.get("reasons", []))
        failed_reason_codes.extend(identity_source_result.get("reason_codes", []))
    price_validity_result = _validate_price_validity(report)
    if not price_validity_result.get("passed", True):
        price_passed = False
        failed_reasons.extend(price_validity_result.get("reasons", []))
        failed_reason_codes.extend(price_validity_result.get("reason_codes", []))
    price_semantic_result = _validate_price_semantics(report)
    if not price_semantic_result.get("passed", True):
        price_passed = False
        failed_reasons.extend(price_semantic_result.get("reasons", []))
        failed_reason_codes.extend(price_semantic_result.get("reason_codes", []))
    trading_day_result = _validate_trading_day_timeliness(report, request_date=request_date)
    if not trading_day_result.get("passed", True):
        trading_day_passed = False
        failed_reasons.extend(trading_day_result.get("reasons", []))
        failed_reason_codes.extend(trading_day_result.get("reason_codes", []))
    expert_outputs = report.get("expert_outputs", {})
    for expert_key, expected_agent in expected_agents.items():
        output = expert_outputs.get(expert_key, {})
        actual_agent = output.get("agent", "")
        output_code = output.get("stock_code", "")
        output_price = _safe_float(output.get("as_of_price"))
        if actual_agent != expected_agent:
            identity_passed = False
            failed_agents.append(expert_key)
            failed_reasons.append(f"{expert_key}身份不匹配: {actual_agent or 'N/A'}")
        if output_code and output_code != stock_code:
            identity_passed = False
            failed_agents.append(expert_key)
            failed_reasons.append(f"{expert_key}标的不一致: {output_code} != {stock_code}")
        if canonical_price > 0 and output_price > 0:
            drift = abs(output_price - canonical_price) / canonical_price
            if drift > EXPERT_PRICE_TOLERANCE_RATIO:
                price_passed = False
                failed_agents.append(expert_key)
                failed_reasons.append(
                    f"{expert_key}价格偏差超阈值({drift * 100:.2f}%>{EXPERT_PRICE_TOLERANCE_RATIO * 100:.1f}%)"
                )
        elif canonical_price > 0 and output_price <= 0:
            price_passed = False
            failed_agents.append(expert_key)
            failed_reasons.append(f"{expert_key}缺失价格锚点")
    passed = identity_passed and price_passed and trading_day_passed
    risks = []
    if not identity_passed:
        risks.append("身份一致性存在风险，需重采并复核代码名称映射")
    if not price_passed:
        risks.append("价格语义一致性存在风险，需核对币种与单位口径")
    if not trading_day_passed:
        risks.append("交易日时效校验未通过，需补齐当日有效行情时间戳")
    if not risks:
        risks.append("未发现身份、价格与交易日时效真实性风险")
    all_evidences = []
    all_evidences.extend(identity_source_result.get("evidences", []))
    all_evidences.extend(price_validity_result.get("evidences", []))
    all_evidences.extend(price_semantic_result.get("evidences", []))
    all_evidences.extend(trading_day_result.get("evidences", []))
    latest_timestamp = "N/A"
    valid_timestamps = []
    for item in all_evidences:
        parsed = _parse_timestamp(item.get("timestamp", ""))
        if parsed:
            valid_timestamps.append(parsed)
    if valid_timestamps:
        latest_timestamp = max(valid_timestamps).strftime("%Y-%m-%d %H:%M")
    unique_failed_reason_codes = list(dict.fromkeys(failed_reason_codes))
    repair_suggestions = _build_repair_suggestions(
        unique_failed_reason_codes,
        stock_code=stock_code,
        canonical_name=report.get("canonical_name", ""),
    )
    return {
        "agent": "expert_identifier_agent",
        "passed": passed,
        "identity_passed": identity_passed,
        "price_passed": price_passed,
        "trading_day_passed": trading_day_passed,
        "require_block": not passed,
        "failed_agents": sorted(set(failed_agents)),
        "failed_reasons": list(dict.fromkeys(failed_reasons)),
        "failed_reason_codes": unique_failed_reason_codes,
        "next_action": "block_and_resample" if not passed else "continue",
        "checked_agents": list(expected_agents.values()),
        "checked_stock_code": stock_code or "N/A",
        "reference_price": f"{canonical_price:.2f}" if canonical_price > 0 else "N/A",
        "identity_source_evidences": identity_source_result.get("evidences", []),
        "price_validity_evidences": price_validity_result.get("evidences", []),
        "price_semantic_evidences": price_semantic_result.get("evidences", []),
        "trading_day_evidences": trading_day_result.get("evidences", []),
        "identity_source_summary": identity_source_result.get("summary", {}),
        "price_validity_summary": price_validity_result.get("summary", {}),
        "price_semantic_summary": price_semantic_result.get("summary", {}),
        "trading_day_summary": trading_day_result.get("summary", {}),
        "repair_suggestions": repair_suggestions,
        "authenticity_summary": {
            "identity_status": "通过" if identity_passed else "未通过",
            "price_status": "通过" if price_passed else "未通过",
            "trading_day_status": "通过" if trading_day_passed else "未通过",
            "source_count": len(all_evidences),
            "latest_timestamp": latest_timestamp,
            "risk_tips": risks,
            "failed_reason_codes": unique_failed_reason_codes,
            "repair_suggestions": repair_suggestions,
        },
    }


def _build_process_block(identity_gate: dict) -> dict:
    failed = identity_gate.get("failed_reasons", [])
    return {
        "blocked": True,
        "blocked_stage": "supervisor_review",
        "reason": "；".join(failed) if failed else "专家身份与价格校验未通过",
        "next_action": "重采样并重新执行专家鉴别",
        "repair_suggestions": identity_gate.get("repair_suggestions", []),
    }


def _build_blocked_supervisor_review(identity_gate: dict) -> dict:
    reason = "；".join(identity_gate.get("failed_reasons", [])) or "专家身份与价格校验未通过"
    return {
        "industry_decision_hint": "观察",
        "event_decision_hint": "观察",
        "conflict_items": ["流程已阻断：专家鉴别失败"],
        "arbitration_reason": reason,
        "result_label_cap": "观察",
        "evidences": [
            {
                "conclusion": "流程阻断",
                "value": reason,
                "source_url": "N/A",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
        ],
        "required_fields_checked": [
            "audit_gate",
            "expert_identity_gate",
            "process_block",
            "evidences",
        ],
    }


def _run_supervisor_review(report: dict, industry_output: dict, event_output: dict) -> dict:
    conflicts = []
    arbitration_reason = "行业与事件信号同向"
    result_label_cap = "可做"
    industry_hint = industry_output.get("decision_hint", "观察")
    event_hint = event_output.get("decision_hint", "观察")
    event_strength = event_output.get("impact_strength", "弱")
    if industry_hint == "可做" and event_hint == "回避":
        result_label_cap = "观察"
        conflicts.append("行业景气偏正向，但事件冲击为负向")
        arbitration_reason = "优先控制短期事件冲击风险"
        if event_strength == "强":
            result_label_cap = "回避"
            conflicts.append("负向事件强度高，触发强制降档")
    elif industry_hint == "回避" and event_hint == "可做":
        result_label_cap = "观察"
        conflicts.append("行业景气承压，但事件短期偏正向")
        arbitration_reason = "避免事件驱动覆盖行业下行风险"
    elif industry_hint == "回避" and event_hint == "回避":
        result_label_cap = "回避"
        arbitration_reason = "行业与事件双负向共振"
    elif industry_hint == "观察" or event_hint == "观察":
        result_label_cap = "观察"
        arbitration_reason = "存在中性信号，保持审慎"
    review_evidences = []
    review_evidences.extend(industry_output.get("evidences", [])[:2])
    review_evidences.extend(event_output.get("evidences", [])[:2])
    normalized_review_evidences = []
    for item in review_evidences:
        normalized_review_evidences.append(
            {
                "conclusion": f"主管复核-{item.get('conclusion', '证据')}",
                "value": item.get("value", "N/A"),
                "source_url": item.get("source_url", "N/A"),
                "timestamp": item.get("timestamp", "N/A"),
            }
        )
    return {
        "industry_decision_hint": industry_hint,
        "event_decision_hint": event_hint,
        "conflict_items": conflicts,
        "arbitration_reason": arbitration_reason,
        "result_label_cap": result_label_cap,
        "evidences": normalized_review_evidences,
        "required_fields_checked": [
            "audit_gate",
            "industry_research_output",
            "event_hunter_output",
            "evidences",
        ],
    }


def _merge_all_evidences(report: dict) -> list:
    merged = []
    merged.extend(report.get("evidences", []))
    expert_outputs = report.get("expert_outputs", {})
    merged.extend(expert_outputs.get("industry_researcher", {}).get("evidences", []))
    merged.extend(expert_outputs.get("event_hunter", {}).get("evidences", []))
    merged.extend(report.get("supervisor_review", {}).get("evidences", []))
    normalized = []
    for item in merged:
        normalized.append(
            {
                "conclusion": item.get("conclusion", "N/A"),
                "value": item.get("value", "N/A"),
                "source_url": item.get("source_url", "N/A"),
                "timestamp": item.get("timestamp", "N/A"),
            }
        )
    return normalized


def format_analysis_report(stock_code: str, stock_name: str, search_data: list) -> str:
    """
    格式化分析报告

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        search_data: Web Search 返回的数据

    Returns:
        格式化的报告文本
    """
    report = parse_search_results_to_report(search_data, stock_code, stock_name=stock_name)

    lines = []
    lines.append("=" * 50)
    lines.append(f"  {stock_name} ({stock_code}) 个股分析报告")
    lines.append("=" * 50)

    # 实时行情
    if report['price_info']:
        lines.append("\n【实时行情】")
        price = report['price_info'].get('price', 'N/A')
        change = report['price_info'].get('change', 'N/A')
        lines.append(f"  当前价格: {price} 元")
        lines.append(f"  涨跌幅: {change}%")

    # 资金流向
    if report['fund_flow']:
        lines.append("\n【资金流向】")
        main = report['fund_flow'].get('main', 'N/A')
        retail = report['fund_flow'].get('retail', 'N/A')
        lines.append(f"  主力资金: {main} 万元")
        lines.append(f"  散户资金: {retail} 万元")

    # 基本面
    if report['financial']:
        lines.append("\n【基本面】")
        news = report['financial'].get('news', '')
        if news:
            lines.append(f"  {news[:100]}...")
        revenue = report['financial'].get('revenue')
        if revenue:
            unit = report['financial'].get('revenue_unit', '')
            lines.append(f"  营业收入: {revenue}{unit}")
        yoy = report['financial'].get('yoy')
        if yoy:
            lines.append(f"  营收同比: {yoy}%")
        qoq = report['financial'].get('qoq')
        if qoq:
            lines.append(f"  营收环比: {qoq}%")

    # 综合建议
    lines.append("\n" + "=" * 50)
    lines.append("  【综合分析建议】")
    lines.append("=" * 50)

    # 基于数据给出建议
    advice = _generate_advice(report)
    lines.append(f"  {advice}")

    lines.append("\n【风险提示】")
    lines.append("  - 股市有风险，投资需谨慎")
    lines.append("  - 本分析仅供参考，不构成投资建议")
    lines.append("  - 建议分散投资，控制仓位")

    lines.append("=" * 50)

    return "\n".join(lines)


def _generate_advice(report: dict) -> str:
    """基于数据生成建议"""
    advice_parts = []

    # 分析资金流向
    fund_flow = report.get('fund_flow', {})
    main = fund_flow.get('main', '0')

    try:
        main_val = float(main)
        if main_val > 0:
            advice_parts.append("主力资金净流入，看多")
        elif main_val < 0:
            advice_parts.append("主力资金净流出，注意风险")
    except Exception:
        pass

    # 分析价格变化
    price_info = report.get('price_info', {})
    change = price_info.get('change', '0')

    try:
        change_val = float(change.replace('%', ''))
        if change_val > 5:
            advice_parts.append("短期涨幅较大，谨慎追高")
        elif change_val < -5:
            advice_parts.append("短期跌幅较大，关注反弹机会")
    except Exception:
        pass

    if not advice_parts:
        return "建议关注基本面和长期走势"

    return "，".join(advice_parts)


def format_obsidian_markdown_report(payload: dict) -> str:
    stocks = payload.get("stocks", [])
    date_text = payload.get("date", datetime.now().strftime("%Y-%m-%d"))
    if payload.get("analysis_mode") == "agent_team":
        mode = "stock_pool"
    elif payload.get("analysis_mode") == "single_flow":
        mode = "single_stock"
    else:
        mode = "single_stock" if len(stocks) <= 1 else "stock_pool"
    if mode == "single_stock":
        return _build_single_stock_markdown(stocks[0] if stocks else {}, date_text)
    return _build_stock_pool_markdown(stocks, date_text)


def plan_analysis_route(user_request: str) -> dict:
    decision = should_use_agent_team(user_request)
    # lite/full 统一走 Team 编排，仅执行强度由 execution_profile 控制
    plan = build_skill_chain_plan(use_team=True)
    return {
        "mode": plan.get("mode", "agent_team"),
        "steps": plan.get("steps", []),
        "reasons": decision.get("reasons", []),
        "execution_profile": decision.get("execution_profile", plan.get("execution_profile", "lite_parallel")),
        "team_rules": plan.get("team_rules", {}),
    }


def get_minimal_shortline_upgrade_advice() -> dict:
    recommendation = get_shortline_indicator_recommendations()
    return {
        "indicator_layers": recommendation.get("layers", {}),
        "code_entry_mapping": recommendation.get("code_entry_mapping", []),
        "minimum_rollout_order": recommendation.get("minimum_rollout_order", []),
        "compatibility_notes": recommendation.get("compatibility_notes", []),
    }


def _build_single_stock_markdown(stock: dict, date_text: str) -> str:
    code = stock.get("stock_code", "000000")
    name = stock.get("stock_name", "未知标的")
    label = stock.get("label", "观察")
    invalid_condition = stock.get("invalid_condition", "跌破止损位")
    price = stock.get("price", "N/A")
    scores = stock.get("scores", {})
    momentum = scores.get("momentum", "N/A")
    revenue = scores.get("revenue", "N/A")
    risk = scores.get("risk", "N/A")
    sentiment_governance = _resolve_sentiment_governance(stock)
    shortline_adjustment = _calc_shortline_adjusted_score(
        scores,
        stock.get("shortline_signals", {}),
        stock.get("audit_gate", {}),
        stock.get("expert_identity_gate", {}),
        sentiment_governance,
    )
    final_score = shortline_adjustment.get("base_score", "N/A")
    adjusted_score = shortline_adjustment.get("adjusted_score", "N/A")
    lines = [
        "---",
        f"title: {code}_{name}_{date_text}",
        f"date: {date_text}",
        f"tags: [A股, 短线营收, 单票分析, {name}]",
        "---",
        "",
        f"# {name}({code}) 短线营收双轨分析报告",
        "",
        "> [!NOTE]",
        f"> **分析日期**: {date_text}",
        f"> **双轨结论**: {label}",
        f"> **信号失效条件**: {invalid_condition}",
        "",
        "## 核心评分",
        "",
        "| 维度 | 分数 |",
        "|------|------|",
        f"| 短线动量分（40%） | {momentum} |",
        f"| 营收质量分（35%） | {revenue} |",
        f"| 风险约束分（25%） | {risk} |",
        f"| 加权总分 | {final_score} |",
        f"| 短线校准后总分 | {adjusted_score} |",
        f"| 舆情调整（封顶±{shortline_adjustment.get('sentiment_cap', f'{SENTIMENT_MAX_IMPACT:.1f}')}分） | {shortline_adjustment.get('sentiment_adjustment', '0.0')} |",
        f"| 加权总分计算 | {_build_score_formula(scores)} |",
        "",
        "## 关键信息",
        "",
        f"- 当前价格：{price}元",
        f"- 结论标签：{label}",
        f"- 置信度：{_derive_confidence(stock)}",
    ]
    lines.extend(_build_data_audit_lines(stock))
    lines.extend(_build_data_source_meta_lines(stock))
    lines.extend(_build_authenticity_verification_lines(stock))
    lines.extend(_build_expert_identity_lines(stock))
    lines.extend(_build_process_block_lines(stock))
    lines.extend(_build_revenue_snapshot_lines(stock))
    lines.extend(_build_shortline_signal_lines(stock))
    lines.extend(_build_industry_research_lines(stock))
    lines.extend(_build_event_hunter_lines(stock))
    lines.extend(_build_supervisor_arbitration_lines(stock))
    lines.extend(_build_sentiment_governance_lines(sentiment_governance))
    warning = _build_reversal_warning(stock)
    if warning:
        lines.extend(["", warning])
    lines.extend(_build_evidence_lines(stock))
    return "\n".join(lines)


def _build_stock_pool_markdown(stocks: list, date_text: str) -> str:
    lines = [
        "---",
        f"title: 股票池_{date_text}_短线营收双轨分析",
        f"date: {date_text}",
        "tags: [A股, 短线营收, 股票池]",
        "---",
        "",
        "# 股票池短线营收双轨分析报告",
        "",
        "> [!NOTE]",
        f"> **分析日期**: {date_text}",
        f"> **覆盖标的数**: {len(stocks)}",
        "",
        "## 股票池总览",
        "",
        "| 代码 | 名称 | 标签 | 加权总分 |",
        "|------|------|------|----------|",
    ]
    for stock in stocks:
        code = stock.get("stock_code", "000000")
        name = stock.get("stock_name", "未知标的")
        label = stock.get("label", "观察")
        sentiment_governance = _resolve_sentiment_governance(stock)
        shortline_adjustment = _calc_shortline_adjusted_score(
            stock.get("scores", {}),
            stock.get("shortline_signals", {}),
            stock.get("audit_gate", {}),
            stock.get("expert_identity_gate", {}),
            sentiment_governance,
        )
        score = shortline_adjustment.get("adjusted_score", "N/A")
        lines.append(f"| {code} | {name} | {label} | {score} |")
    lines.append("")
    for stock in stocks:
        code = stock.get("stock_code", "000000")
        name = stock.get("stock_name", "未知标的")
        sentiment_governance = _resolve_sentiment_governance(stock)
        lines.extend([
            f"## {name}({code})",
            "",
            f"- 标签：{stock.get('label', '观察')}",
            f"- 加权总分：{_calc_weighted_score(stock.get('scores', {}))}",
            f"- 短线校准后总分：{_calc_shortline_adjusted_score(stock.get('scores', {}), stock.get('shortline_signals', {}), stock.get('audit_gate', {}), stock.get('expert_identity_gate', {}), sentiment_governance).get('adjusted_score', 'N/A')}",
            f"- 加权总分计算：{_build_score_formula(stock.get('scores', {}))}",
            f"- 置信度：{_derive_confidence(stock)}",
        ])
        lines.extend(_build_data_audit_lines(stock))
        lines.extend(_build_data_source_meta_lines(stock))
        lines.extend(_build_authenticity_verification_lines(stock))
        lines.extend(_build_expert_identity_lines(stock))
        lines.extend(_build_process_block_lines(stock))
        lines.extend(_build_revenue_snapshot_lines(stock))
        lines.extend(_build_shortline_signal_lines(stock))
        lines.extend(_build_industry_research_lines(stock))
        lines.extend(_build_event_hunter_lines(stock))
        lines.extend(_build_supervisor_arbitration_lines(stock))
        lines.extend(_build_sentiment_governance_lines(sentiment_governance))
        warning = _build_reversal_warning(stock)
        if warning:
            lines.extend(["", warning])
        lines.extend(_build_evidence_lines(stock))
        lines.append("")
    return "\n".join(lines).strip()


def _build_reversal_warning(stock: dict) -> str:
    fund_flow = stock.get("fund_flow", {})
    latest_main = _safe_float(fund_flow.get("latest_main", 0))
    five_day_main = _safe_float(fund_flow.get("five_day_main", 0))
    if five_day_main > 0 and latest_main < 0:
        return (
            "> [!WARNING] 资金流向反转预警\n"
            f"> - 标的：{stock.get('stock_name', '未知标的')}({stock.get('stock_code', '000000')})\n"
            f"> - 近5日主力资金：净流入{five_day_main:.2f}万元\n"
            f"> - 最新主力资金：净流出{abs(latest_main):.2f}万元\n"
            "> - **方向反转**，需下调短线仓位或等待二次确认"
        )
    return ""


def _build_shortline_signal_lines(stock: dict) -> list:
    recommendation = _generate_minimal_shortline_recommendation(stock)
    signals = recommendation.get("signals", {})
    missing = recommendation.get("missing", [])
    label_cap = recommendation.get("label_cap", "可做")
    downgrade_reasons = recommendation.get("downgrade_reasons", [])
    lines = [
        "",
        "## 短线信号确认",
        "",
        f"- VWAP偏离：{signals.get('vwap_deviation', 'N/A')}%",
        f"- ATR止损：{signals.get('atr_stop', 'N/A')}",
        f"- 量比：{signals.get('volume_ratio', 'N/A')}",
    ]
    if downgrade_reasons:
        lines.append(f"- 降级原因：{'; '.join(downgrade_reasons)}")
        lines.append(f"- 建议上限标签：{label_cap}")
    elif missing:
        lines.append(f"- 降级原因：缺失关键指标 {','.join(missing)}")
        lines.append(f"- 建议上限标签：{label_cap}")
    elif label_cap != "可做":
        lines.append("- 降级原因：VWAP偏离过大且量比不足，确认信号偏弱")
        lines.append(f"- 建议上限标签：{label_cap}")
    else:
        lines.append("- 降级原因：无")
    return lines


def _generate_minimal_shortline_recommendation(stock: dict) -> dict:
    signals = stock.get("shortline_signals", {})
    audit_gate = stock.get("audit_gate", {})
    identity_gate = stock.get("expert_identity_gate", {})
    required_keys = ["vwap_deviation", "atr_stop", "volume_ratio"]
    missing = [key for key in required_keys if str(signals.get(key, "")).strip() in ("", "N/A", "未知")]
    vwap_val = abs(_safe_float(signals.get("vwap_deviation")))
    volume_ratio_val = _safe_float(signals.get("volume_ratio"))
    weak_confirmation = (vwap_val >= 4.0 and 0 < volume_ratio_val < 1.0)
    label_cap = "可做"
    confidence_cap = "高"
    downgrade_reasons = []
    if not audit_gate.get("passed", True):
        label_cap = "观察"
        confidence_cap = "低"
        downgrade_reasons.extend(audit_gate.get("downgrade_reasons", []))
        if audit_gate.get("require_resample"):
            downgrade_reasons.append("数据真实性审计未通过，需先重采再评估")
    if identity_gate and not identity_gate.get("passed", True):
        label_cap = "回避"
        confidence_cap = "低"
        downgrade_reasons.append("专家身份与价格校验未通过，流程阻断")
        downgrade_reasons.extend(identity_gate.get("failed_reasons", []))
    if weak_confirmation:
        label_cap = "回避"
        confidence_cap = "低"
        downgrade_reasons.append("VWAP偏离过大且量比不足，确认信号偏弱")
    elif missing:
        label_cap = "观察"
        confidence_cap = "中" if confidence_cap != "低" else confidence_cap
        downgrade_reasons.append(f"缺失关键指标 {','.join(missing)}")
    return {
        "signals": {
            "vwap_deviation": signals.get("vwap_deviation", "N/A"),
            "atr_stop": signals.get("atr_stop", "N/A"),
            "volume_ratio": signals.get("volume_ratio", "N/A"),
        },
        "missing": missing,
        "label_cap": label_cap,
        "confidence_cap": confidence_cap,
        "downgrade_reasons": list(dict.fromkeys(downgrade_reasons)),
    }


def _calc_weighted_score(scores: dict):
    momentum = _safe_float(scores.get("momentum"))
    revenue = _safe_float(scores.get("revenue"))
    risk = _safe_float(scores.get("risk"))
    if momentum == 0 and revenue == 0 and risk == 0:
        return "N/A"
    total = momentum * 0.4 + revenue * 0.35 + risk * 0.25
    return f"{total:.1f}"


def _calc_shortline_adjusted_score(
    scores: dict,
    shortline_signals: dict,
    audit_gate: dict = None,
    expert_identity_gate: dict = None,
    sentiment_governance: dict = None,
) -> dict:
    base_score_text = _calc_weighted_score(scores)
    if base_score_text == "N/A":
        return {"base_score": "N/A", "adjusted_score": "N/A"}
    base_score = _safe_float(base_score_text)
    recommendation = _generate_minimal_shortline_recommendation(
        {
            "shortline_signals": shortline_signals,
            "audit_gate": audit_gate or {},
            "expert_identity_gate": expert_identity_gate or {},
        }
    )
    missing = recommendation.get("missing", [])
    label_cap = recommendation.get("label_cap", "可做")
    downgrade_reasons = recommendation.get("downgrade_reasons", [])
    adjusted = base_score
    if label_cap == "回避":
        adjusted = base_score - 15
    elif missing or downgrade_reasons:
        adjusted = base_score - 5
    elif label_cap == "可做":
        adjusted = min(base_score + 3, 100)
    sentiment_adjustment = _resolve_sentiment_adjustment(sentiment_governance or {})
    adjusted += sentiment_adjustment
    adjusted = min(max(adjusted, 0), 100)
    return {
        "base_score": f"{base_score:.1f}",
        "adjusted_score": f"{adjusted:.1f}",
        "sentiment_adjustment": f"{sentiment_adjustment:.1f}",
        "sentiment_cap": f"{SENTIMENT_MAX_IMPACT:.1f}",
    }


def _build_score_formula(scores: dict) -> str:
    momentum = _safe_float(scores.get("momentum"))
    revenue = _safe_float(scores.get("revenue"))
    risk = _safe_float(scores.get("risk"))
    total = momentum * 0.4 + revenue * 0.35 + risk * 0.25
    return f"{momentum:.1f}×40% + {revenue:.1f}×35% + {risk:.1f}×25% = {total:.1f}"


def _derive_confidence(stock: dict) -> str:
    audit_gate = stock.get("audit_gate", {})
    if audit_gate and not audit_gate.get("passed", True):
        return "低"
    identity_gate = stock.get("expert_identity_gate", {})
    if identity_gate and not identity_gate.get("passed", True):
        return "低"
    snapshot = stock.get("revenue_snapshot", {})
    required_fields = ["revenue", "yoy", "qoq"]
    valid_count = 0
    for field in required_fields:
        value = str(snapshot.get(field, "")).strip()
        if value and value not in ("N/A", "-", "未知"):
            valid_count += 1
    if valid_count == 3:
        return "高"
    if valid_count >= 1:
        return "中"
    return "低"


def _build_authenticity_verification_lines(stock: dict) -> list:
    gate = stock.get("expert_identity_gate", {})
    summary = stock.get("authenticity_verification", {}) or gate.get("authenticity_summary", {})
    if not gate and not summary:
        return []
    identity_status = summary.get("identity_status", "通过" if gate.get("identity_passed", False) else "未通过")
    price_status = summary.get("price_status", "通过" if gate.get("price_passed", False) else "未通过")
    trading_day_status = summary.get("trading_day_status", "通过" if gate.get("trading_day_passed", False) else "未通过")
    source_count = summary.get("source_count", 0)
    latest_timestamp = summary.get("latest_timestamp", "N/A")
    reason_codes = summary.get("failed_reason_codes", gate.get("failed_reason_codes", []))
    identity_summary = gate.get("identity_source_summary", {})
    price_summary = gate.get("price_semantic_summary", {})
    lines = [
        "",
        "## 数据真实性鉴别结果",
        "",
        f"- 身份校验结果：{identity_status}",
        f"- 价格校验结果：{price_status}",
        f"- 交易日时效结果：{trading_day_status}",
        f"- 来源证据条数：{source_count}",
        f"- 最近校验时间戳：{latest_timestamp}",
        (
            f"- 来源摘要：身份证据{identity_summary.get('evidence_count', 0)}条/"
            f"{identity_summary.get('category_count', 0)}类；"
            f"币种单位证据{price_summary.get('record_count', 0)}条/"
            f"{price_summary.get('category_count', 0)}类"
        ),
        f"- 币种/单位：{price_summary.get('currency', 'N/A')} / {price_summary.get('unit', 'N/A')}",
    ]
    if reason_codes:
        lines.append(f"- 失败原因编码：{'; '.join(reason_codes)}")
        mapped_tips = []
        for code in reason_codes:
            tip = FAILURE_REASON_TIPS.get(str(code), "")
            if tip and tip not in mapped_tips:
                mapped_tips.append(tip)
        if mapped_tips:
            lines.append(f"- 用户提示：{'；'.join(mapped_tips)}")
    risks = summary.get("risk_tips", [])
    if risks:
        lines.append(f"- 风险提示：{'; '.join(risks)}")
    return lines


def _build_data_source_meta_lines(stock: dict) -> list:
    router = stock.get("eastmoney_router", {})
    metadata = (
        stock.get("metadata_passthrough")
        or stock.get("symbol_metadata")
        or router.get("metadata_passthrough", {})
    )
    gate = router.get("critical_gate", {})
    if not metadata and not gate:
        return []
    lines = [
        "",
        "## 数据源元信息",
        "",
    ]
    if metadata:
        lines.extend(
            [
                f"- 来源函数：{metadata.get('source_function', 'N/A')}",
                f"- 抓取时间：{metadata.get('fetched_at', 'N/A')}",
                f"- 校验结论：{metadata.get('validation_conclusion', 'N/A')}",
            ]
        )
    reason_codes = gate.get("reason_codes", [])
    user_tips = gate.get("user_tips", [])
    if reason_codes:
        lines.append(f"- 路由失败原因码：{'; '.join(reason_codes)}")
    if not user_tips and reason_codes:
        mapped = []
        for code in reason_codes:
            tip = FAILURE_REASON_TIPS.get(str(code), "")
            if tip and tip not in mapped:
                mapped.append(tip)
        user_tips = mapped
    if user_tips:
        lines.append(f"- 路由用户提示：{'；'.join(user_tips)}")
    if metadata and metadata.get("failure_code"):
        lines.append(f"- 元信息失败原因码：{metadata.get('failure_code')}")
        fallback_tip = FAILURE_REASON_TIPS.get(str(metadata.get("failure_code")), "")
        if fallback_tip:
            lines.append(f"- 元信息用户提示：{fallback_tip}")
    return lines


def _build_data_audit_lines(stock: dict) -> list:
    gate = stock.get("audit_gate", {})
    if not gate:
        return []
    status = "通过" if gate.get("passed", False) else "未通过"
    lines = [
        "",
        "## 数据真实性审计",
        "",
        f"- 审计状态：{status}",
        f"- 是否重采：{'是' if gate.get('require_resample') else '否'}",
    ]
    reasons = gate.get("downgrade_reasons", [])
    if reasons:
        lines.append(f"- 降级原因：{'; '.join(reasons)}")
    field_results = gate.get("field_results", {})
    if field_results:
        lines.extend([
            "",
            "| 字段 | 一致性 | 来源数 | 类别数 | 结论 |",
            "|------|--------|--------|--------|------|",
        ])
        for field, result in field_results.items():
            lines.append(
                f"| {field} | {result.get('consistency', 'N/A')} | {result.get('source_count', 0)} | "
                f"{result.get('category_count', 0)} | {result.get('reason', 'N/A')} |"
            )
    return lines


def _build_expert_identity_lines(stock: dict) -> list:
    gate = stock.get("expert_identity_gate", {})
    if not gate:
        return []
    status = "通过" if gate.get("passed", False) else "未通过"
    lines = [
        "",
        "## 专家鉴别与身份价格校验",
        "",
        f"- 鉴别状态：{status}",
        f"- 身份校验：{'通过' if gate.get('identity_passed', False) else '未通过'}",
        f"- 价格校验：{'通过' if gate.get('price_passed', False) else '未通过'}",
        f"- 校验股票代码：{gate.get('checked_stock_code', 'N/A')}",
        f"- 价格锚点：{gate.get('reference_price', 'N/A')}元",
    ]
    failed_agents = gate.get("failed_agents", [])
    if failed_agents:
        lines.append(f"- 失败专家：{','.join(failed_agents)}")
    failed_reasons = gate.get("failed_reasons", [])
    if failed_reasons:
        lines.append(f"- 失败原因：{'; '.join(failed_reasons)}")
    return lines


def _build_process_block_lines(stock: dict) -> list:
    process_block = stock.get("process_block", {})
    if not process_block:
        return []
    blocked = process_block.get("blocked", False)
    lines = [
        "",
        "## 流程阻断",
        "",
        f"- 阻断状态：{'已阻断' if blocked else '未阻断'}",
    ]
    if blocked:
        lines.append(f"- 阻断阶段：{process_block.get('blocked_stage', 'N/A')}")
        lines.append(f"- 阻断原因：{process_block.get('reason', 'N/A')}")
        lines.append(f"- 后续动作：{process_block.get('next_action', 'N/A')}")
        suggestions = process_block.get("repair_suggestions", [])
        if suggestions:
            lines.append(f"- 修复建议数：{len(suggestions)}")
    return lines


def _build_revenue_snapshot_lines(stock: dict) -> list:
    snapshot = stock.get("revenue_snapshot", {})
    if not snapshot:
        return []
    revenue = snapshot.get("revenue", "N/A")
    yoy = snapshot.get("yoy", "N/A")
    qoq = snapshot.get("qoq", "N/A")
    caliber = snapshot.get("caliber", "未知")
    date = snapshot.get("as_of", "未知")
    return [
        "",
        "## 营收快照",
        "",
        "| 字段 | 数值 |",
        "|------|------|",
        f"| 营业收入 | {revenue} |",
        f"| 同比增速 | {yoy} |",
        f"| 环比增速 | {qoq} |",
        f"| 口径 | {caliber} |",
        f"| 日期 | {date} |",
    ]


def _build_industry_research_lines(stock: dict) -> list:
    output = _resolve_industry_output(stock)
    if not output:
        return []
    return [
        "",
        "## 行业研究家结论",
        "",
        f"- 景气结论：{output.get('outlook', 'N/A')}",
        f"- 景气拐点：{output.get('inflection', 'N/A')}",
        f"- 竞争格局：{output.get('competition_landscape', 'N/A')}",
        f"- 决策建议：{output.get('decision_hint', '观察')}",
    ]


def _build_event_hunter_lines(stock: dict) -> list:
    output = _resolve_event_output(stock)
    if not output:
        return []
    return [
        "",
        "## 消息面猎手结论",
        "",
        f"- 事件方向：{output.get('impact_direction', '中性')}",
        f"- 冲击强度：{output.get('impact_strength', '弱')}",
        f"- 时效窗口：{output.get('time_window', 'N/A')}",
        f"- 监管信号：{output.get('regulatory_signal', '低')}",
        f"- 决策建议：{output.get('decision_hint', '观察')}",
    ]


def _build_supervisor_arbitration_lines(stock: dict) -> list:
    review = _resolve_supervisor_review(stock)
    if not review:
        return []
    conflicts = review.get("conflict_items", [])
    lines = [
        "",
        "## 主管裁决与冲突仲裁",
        "",
        f"- 行业建议：{review.get('industry_decision_hint', '观察')}",
        f"- 事件建议：{review.get('event_decision_hint', '观察')}",
        f"- 仲裁结论标签上限：{review.get('result_label_cap', '观察')}",
        f"- 仲裁原因：{review.get('arbitration_reason', 'N/A')}",
    ]
    if conflicts:
        lines.append(f"- 冲突项：{'; '.join(conflicts)}")
    else:
        lines.append("- 冲突项：无")
    return lines


def _build_evidence_lines(stock: dict) -> list:
    evidences = stock.get("evidences", [])
    if not evidences:
        return []
    lines = [
        "",
        "## 证据链",
        "",
        "| 结论 | 数据点 | 来源URL | 时间戳 |",
        "|------|--------|---------|--------|",
    ]
    for item in evidences:
        conclusion = item.get("conclusion", "N/A")
        value = item.get("value", "N/A")
        source_url = item.get("source_url", "N/A")
        timestamp = item.get("timestamp", "N/A")
        lines.append(f"| {conclusion} | {value} | {source_url} | {timestamp} |")
    return lines


def _resolve_industry_output(stock: dict) -> dict:
    output = stock.get("industry_research_output", {})
    if output:
        return output
    return stock.get("expert_outputs", {}).get("industry_researcher", {})


def _resolve_event_output(stock: dict) -> dict:
    output = stock.get("event_hunter_output", {})
    if output:
        return output
    return stock.get("expert_outputs", {}).get("event_hunter", {})


def _resolve_supervisor_review(stock: dict) -> dict:
    review = stock.get("supervisor_review", {})
    if review:
        return review
    identity_gate = stock.get("expert_identity_gate", {})
    if identity_gate and not identity_gate.get("passed", True):
        return _build_blocked_supervisor_review(identity_gate)
    industry_output = _resolve_industry_output(stock)
    event_output = _resolve_event_output(stock)
    if not industry_output and not event_output:
        return {}
    return _run_supervisor_review(stock, industry_output, event_output)


def _resolve_sentiment_adjustment(sentiment_governance: dict) -> float:
    raw = _safe_float(sentiment_governance.get("score_adjustment", 0.0))
    if raw > SENTIMENT_MAX_IMPACT:
        return SENTIMENT_MAX_IMPACT
    if raw < -SENTIMENT_MAX_IMPACT:
        return -SENTIMENT_MAX_IMPACT
    return raw


def _resolve_sentiment_governance(stock: dict) -> dict:
    governance = stock.get("sentiment_governance", {})
    if governance:
        return governance
    news = stock.get("news", [])
    if news:
        return _govern_news_sentiment(news)
    return {}


def _build_sentiment_governance_lines(sentiment_governance: dict) -> list:
    if not sentiment_governance:
        return []
    lines = [
        "",
        "## 舆情降噪治理",
        "",
        f"- 去重条数：{sentiment_governance.get('deduped_count', 0)}",
        f"- 采纳条数：{sentiment_governance.get('accepted_count', 0)}",
        f"- 剔除条数：{sentiment_governance.get('rejected_count', 0)}",
        f"- 平均质量分：{sentiment_governance.get('average_quality_score', '0.0')}",
        f"- 舆情原始倾向分：{sentiment_governance.get('sentiment_score_raw', '0.00')}",
        (
            f"- 综合评分影响：{sentiment_governance.get('score_adjustment', '0.0')} "
            f"(封顶±{sentiment_governance.get('max_impact_cap', f'{SENTIMENT_MAX_IMPACT:.1f}')})"
        ),
    ]
    accepted_items = sentiment_governance.get("accepted_items", [])
    if accepted_items:
        lines.append("- 采纳依据：")
        for item in accepted_items[:3]:
            reason_text = "；".join(item.get("reasons", [])) or "质量达标"
            lines.append(
                f"  - {item.get('title', 'N/A')}（质量分{item.get('quality_score', 0)}，依据：{reason_text}）"
            )
    rejected_items = sentiment_governance.get("rejected_items", [])
    if rejected_items:
        lines.append("- 剔除依据：")
        for item in rejected_items[:3]:
            lines.append(
                f"  - {item.get('title', 'N/A')}（质量分{item.get('quality_score', 0)}，原因：{item.get('reason', '质量不达标')}）"
            )
    return lines


def _safe_float(value):
    try:
        return float(value)
    except Exception:
        return 0.0


if __name__ == "__main__":
    # 测试解析
    test_data = [
        {
            "title": "珠江股份(600684) 股价",
            "snippet": "最新价4.85元，当日下跌0.82%",
            "link": "http://example.com"
        },
        {
            "title": "资金流向",
            "snippet": "主力资金净流出107.98万元，散户资金呈净流入状态",
            "link": "http://example.com"
        }
    ]

    print(format_analysis_report("600684", "珠江股份", test_data))
