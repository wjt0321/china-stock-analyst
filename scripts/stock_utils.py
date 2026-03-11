# A股分析辅助脚本
# 本脚本作为辅助工具，主要数据获取通过 Web Search 完成

# 股票代码正则验证
import re
from datetime import datetime

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
