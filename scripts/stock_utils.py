# A股分析辅助脚本
# 本脚本作为辅助工具，主要数据获取通过 Web Search 完成

# 股票代码正则验证
import re
from datetime import datetime
from urllib.parse import urlparse

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
        "required_categories": 3,
        "timestamp_conflict_threshold_minutes": 90,
        "category_hints": {
            "交易所/监管": ["sse.com.cn", "szse.cn", "cninfo.com.cn", "csrc.gov.cn"],
            "行情终端": ["eastmoney.com", "10jqka.com.cn", "cls.cn", "stcn.com"],
            "财经媒体": ["stcn.com", "caixin.com", "yicai.com", "cnstock.com"],
            "券商研报": ["cmschina.com", "htsc.com.cn", "citics.com"],
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
