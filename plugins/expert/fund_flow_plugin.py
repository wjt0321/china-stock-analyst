"""
示例插件 - 资金流向分析插件
"""

import logging
from typing import Dict, Any

try:
    from plugin_base import ExpertPlugin, PluginContext, PluginResult
    from akshare_adapter import AKShareAdapter, format_fund_flow_summary
except ImportError:
    from scripts.plugin_base import ExpertPlugin, PluginContext, PluginResult
    from scripts.akshare_adapter import AKShareAdapter, format_fund_flow_summary

LOGGER = logging.getLogger(__name__)


class FundFlowPlugin(ExpertPlugin):
    """资金流向分析插件"""

    name = "fund_flow"
    version = "1.0.0"
    description = "分析主力资金、超大单、大单等资金流向"
    author = "China Stock Analyst"
    category = "flow"
    priority = 95
    enabled = True
    requires_akshare = True

    def __init__(self):
        self.adapter = None

    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化"""
        try:
            self.adapter = AKShareAdapter()
            return True
        except Exception as e:
            LOGGER.error(f"初始化失败: {e}")
            return False

    def can_handle(self, context: PluginContext) -> bool:
        """判断是否能处理请求"""
        request = context.request.lower()
        keywords = ["资金", "主力", "流入", "流出", "超大单", "大单"]
        return any(keyword in request for keyword in keywords)

    def execute(self, context: PluginContext) -> PluginResult:
        """执行资金流向分析"""
        result = PluginResult()

        if not context.stock_code:
            result.errors.append("需要股票代码")
            return result

        if not self.adapter:
            result.errors.append("插件未初始化")
            return result

        try:
            data = self.adapter.get_full_data(context.stock_code)

            if not data.success or not data.fund_flow:
                result.errors.append("无法获取资金流向数据")
                return result

            # 获取资金流向摘要
            summary = format_fund_flow_summary(data.fund_flow)
            latest_flow = data.fund_flow[0] if data.fund_flow else None

            # 构建结果
            result.success = True
            result.data = {
                "stock_code": context.stock_code,
                "stock_name": data.stock_name,
                "fund_flow": data.fund_flow,
                "summary": summary,
                "latest": latest_flow,
            }

            # 生成分析内容
            result.content = self._generate_analysis_content(
                context.stock_code, data.stock_name, data.fund_flow, summary
            )

        except Exception as e:
            LOGGER.error(f"执行失败: {e}")
            result.errors.append(f"执行异常: {str(e)}")

        return result

    def _generate_analysis_content(self, stock_code: str, stock_name: str, fund_flow: list, summary: dict) -> str:
        """生成资金流向分析内容"""
        content = []
        content.append(f"## {stock_name}({stock_code}) 资金流向分析\n")

        # 最新资金数据
        if fund_flow:
            latest = fund_flow[0]
            content.append(f"**日期**: {latest['date']}")
            content.append(f"**收盘价**: {latest['close_price']:.2f} 元")
            content.append(f"**涨跌幅**: {latest['change_pct']:.2f}%\n")

        # 资金流向摘要
        if summary:
            content.append("### 近5日资金流向")
            direction_emoji = "📈" if summary.get("direction") == "流入" else "📉"
            content.append(f"{direction_emoji} **方向**: {summary.get('direction', '未知')}")
            content.append(f"💪 **强度**: {summary.get('intensity', '未知')}")
            content.append(f"💰 **主力净流入**: {abs(summary.get('total_net', 0) / 100000000):.2f} 亿")
            content.append(f"📊 **平均净占比**: {summary.get('avg_net_pct', 0):.2f}%\n")

        # 详细资金分类（近5日）
        content.append("### 近5日详细资金分类")
        for flow in fund_flow[:5]:
            date = flow.get("date", "")
            main = flow.get("main_net_inflow", 0)
            super = flow.get("super_net_inflow", 0)
            big = flow.get("big_net_inflow", 0)
            content.append(f"- **{date}**:")
            content.append(f"  - 主力: {main / 10000:.1f} 万")
            content.append(f"  - 超大单: {super / 10000:.1f} 万")
            content.append(f"  - 大单: {big / 10000:.1f} 万")

        return "\n".join(content)
