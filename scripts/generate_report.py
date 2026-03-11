import re
from datetime import datetime
from team_router import should_use_agent_team, build_skill_chain_plan


def parse_search_results_to_report(search_results: list, stock_code: str) -> dict:
    """
    将搜索结果解析为结构化报告数据

    Args:
        search_results: Web Search 返回的结果列表
        stock_code: 股票代码

    Returns:
        包含解析后数据的字典
    """
    report = {
        "stock_code": stock_code,
        "price_info": {},
        "fund_flow": {},
        "financial": {},
        "news": []
    }

    for result in search_results:
        title = result.get('title', '')
        snippet = result.get('snippet', '')
        link = result.get('link', '')

        # 解析价格信息
        if '最新价' in snippet or '股价' in title:
            _parse_price(snippet, report['price_info'])

        # 解析资金流向
        if '资金流向' in title or '主力' in snippet:
            _parse_fund_flow(snippet, report['fund_flow'])

        if (
            '净利润' in snippet or '业绩' in title or '预增' in snippet
            or '营业收入' in snippet or '同比' in snippet or '环比' in snippet
        ):
            _parse_financial(snippet, report['financial'])

        # 保存新闻
        report['news'].append({
            'title': title,
            'snippet': snippet[:150],
            'link': link
        })

    return report


def _parse_price(snippet: str, price_info: dict):

    # 匹配价格
    price_pattern = r'(\d+\.?\d*)\s*元'
    price_match = re.search(price_pattern, snippet)
    if price_match:
        price_info['price'] = price_match.group(1)

    # 匹配涨跌幅
    change_pattern = r'([+-]?\d+\.?\d*)\s*%'
    change_match = re.search(change_pattern, snippet)
    if change_match:
        price_info['change'] = change_match.group(1)


def _parse_fund_flow(snippet: str, fund_flow: dict):
    main = _extract_flow_amount(snippet, '主力')
    if main is not None:
        fund_flow['main'] = f"{main:.2f}"
    retail = _extract_flow_amount(snippet, '散户')
    if retail is not None:
        fund_flow['retail'] = f"{retail:.2f}"


def _extract_flow_amount(snippet: str, role: str):
    pattern = rf'{role}[资金]*[^，。,；;]*?(净流入|净流出)?\s*([+-]?\d+\.?\d*)\s*(亿元|亿|万元|万|元)?'
    match = re.search(pattern, snippet)
    if not match:
        return None
    direction = match.group(1) or ''
    amount_raw = float(match.group(2))
    unit = match.group(3) or '万元'
    amount = _normalize_to_wan(amount_raw, unit)
    if direction == '净流出':
        amount = -abs(amount)
    elif direction == '净流入':
        amount = abs(amount)
    return amount


def _normalize_to_wan(value: float, unit: str) -> float:
    if unit in ('亿元', '亿'):
        return value * 10000
    if unit in ('元',):
        return value / 10000
    return value


def _parse_financial(snippet: str, financial: dict):
    financial['news'] = snippet[:200]
    revenue_match = re.search(r'营业收入[^0-9]*([0-9]+\.?[0-9]*)\s*(亿元|亿|万元|万|元)', snippet)
    if revenue_match:
        financial['revenue'] = f"{float(revenue_match.group(1)):.2f}"
        financial['revenue_unit'] = revenue_match.group(2)
    yoy_match = re.search(r'同比(?:增长|下降)?\s*([+-]?[0-9]+\.?[0-9]*)\s*%', snippet)
    if yoy_match:
        financial['yoy'] = f"{float(yoy_match.group(1)):.2f}"
    qoq_match = re.search(r'环比(?:增长|下降)?\s*([+-]?[0-9]+\.?[0-9]*)\s*%', snippet)
    if qoq_match:
        financial['qoq'] = f"{float(qoq_match.group(1)):.2f}"
    financial['as_of'] = datetime.now().strftime('%Y-%m-%d')


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
    report = parse_search_results_to_report(search_data, stock_code)

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
    plan = build_skill_chain_plan(use_team=decision.get("use_team", False))
    return {
        "mode": plan.get("mode", "single_flow"),
        "steps": plan.get("steps", []),
        "reasons": decision.get("reasons", []),
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
    final_score = _calc_weighted_score(scores)
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
        f"| 加权总分计算 | {_build_score_formula(scores)} |",
        "",
        "## 关键信息",
        "",
        f"- 当前价格：{price}元",
        f"- 结论标签：{label}",
        f"- 置信度：{_derive_confidence(stock)}",
    ]
    lines.extend(_build_revenue_snapshot_lines(stock))
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
        score = _calc_weighted_score(stock.get("scores", {}))
        lines.append(f"| {code} | {name} | {label} | {score} |")
    lines.append("")
    for stock in stocks:
        code = stock.get("stock_code", "000000")
        name = stock.get("stock_name", "未知标的")
        lines.extend([
            f"## {name}({code})",
            "",
            f"- 标签：{stock.get('label', '观察')}",
            f"- 加权总分：{_calc_weighted_score(stock.get('scores', {}))}",
            f"- 加权总分计算：{_build_score_formula(stock.get('scores', {}))}",
            f"- 置信度：{_derive_confidence(stock)}",
        ])
        lines.extend(_build_revenue_snapshot_lines(stock))
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


def _calc_weighted_score(scores: dict):
    momentum = _safe_float(scores.get("momentum"))
    revenue = _safe_float(scores.get("revenue"))
    risk = _safe_float(scores.get("risk"))
    if momentum == 0 and revenue == 0 and risk == 0:
        return "N/A"
    total = momentum * 0.4 + revenue * 0.35 + risk * 0.25
    return f"{total:.1f}"


def _build_score_formula(scores: dict) -> str:
    momentum = _safe_float(scores.get("momentum"))
    revenue = _safe_float(scores.get("revenue"))
    risk = _safe_float(scores.get("risk"))
    total = momentum * 0.4 + revenue * 0.35 + risk * 0.25
    return f"{momentum:.1f}×40% + {revenue:.1f}×35% + {risk:.1f}×25% = {total:.1f}"


def _derive_confidence(stock: dict) -> str:
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
