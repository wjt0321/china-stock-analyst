"""
示例插件 - 技术指标分析插件
"""

import logging
from typing import Dict, Any

try:
    from plugin_base import ExpertPlugin, PluginContext, PluginResult
    from technical_indicators import calc_full_indicators
    from akshare_adapter import AKShareAdapter
except ImportError:
    from scripts.plugin_base import ExpertPlugin, PluginContext, PluginResult
    from scripts.technical_indicators import calc_full_indicators
    from scripts.akshare_adapter import AKShareAdapter

LOGGER = logging.getLogger(__name__)


class TechnicalIndicatorsPlugin(ExpertPlugin):
    """技术指标分析插件"""

    name = "technical_indicators"
    version = "1.0.0"
    description = "自动计算并分析技术指标（ATR/VWAP/RSI等）"
    author = "China Stock Analyst"
    category = "technical"
    priority = 90
    enabled = True
    requires_akshare = True

    def __init__(self):
        self.adapter = None

    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化 AKShare 适配器"""
        try:
            self.adapter = AKShareAdapter()
            return True
        except Exception as e:
            LOGGER.error(f"初始化失败: {e}")
            return False

    def can_handle(self, context: PluginContext) -> bool:
        """判断是否能处理请求"""
        request = context.request.lower()
        keywords = ["技术", "指标", "atr", "vwap", "rsi", "量比", "动量"]
        return any(keyword in request for keyword in keywords)

    def execute(self, context: PluginContext) -> PluginResult:
        """执行技术指标分析"""
        result = PluginResult()

        if not context.stock_code:
            result.errors.append("需要股票代码")
            return result

        if not self.adapter:
            result.errors.append("插件未初始化")
            return result

        try:
            # 获取 K 线数据
            data = self.adapter.get_full_data(context.stock_code)
            if not data.success or not data.candles:
                result.errors.append("无法获取 K 线数据")
                return result

            # 计算完整技术指标
            indicators = calc_full_indicators(data.candles)

            if not indicators:
                result.errors.append("技术指标计算失败")
                return result

            # 构建分析结果
            result.success = True
            result.data = {
                "stock_code": context.stock_code,
                "stock_name": data.stock_name,
                "indicators": indicators,
                "candles_count": len(data.candles),
            }

            # 生成分析内容
            result.content = self._generate_analysis_content(
                context.stock_code, data.stock_name, indicators
            )

        except Exception as e:
            LOGGER.error(f"执行失败: {e}")
            result.errors.append(f"执行异常: {str(e)}")

        return result

    def _generate_analysis_content(self, stock_code: str, stock_name: str, indicators: dict) -> str:
        """生成技术指标分析内容"""
        content = []
        content.append(f"## {stock_name}({stock_code}) 技术指标分析\n")

        # 价格信息
        if indicators.get("price"):
            content.append(f"**当前价格**: {indicators['price']:.2f} 元\n")

        # 趋势判断
        bullish = 0
        bearish = 0

        # ATR 分析
        atr = indicators.get("atr")
        if atr:
            content.append("### ATR 波动率")
            content.append(f"- ATR(14): {atr.atr:.2f} 元")
            content.append(f"- 波动率: {((atr.atr / indicators['price']) * 100):.2f}%\n")
            if atr.atr > 0:
                bullish += 1

        # VWAP 分析
        vwap = indicators.get("vwap")
        if vwap:
            content.append("### VWAP 成交量加权均价")
            content.append(f"- VWAP: {vwap.vwap:.2f} 元")
            content.append(f"- 偏离: {vwap.deviation:.2f} 元 ({vwap.deviation_pct:.2f}%)")
            if vwap.deviation_pct < -2:
                content.append("- 价格低于 VWAP，有反弹空间")
                bullish += 1
            elif vwap.deviation_pct > 2:
                content.append("- 价格高于 VWAP，注意回调风险")
                bearish += 1
            content.append("")

        # RSI 分析
        rsi = indicators.get("rsi")
        if rsi is not None:
            content.append("### RSI 相对强弱")
            content.append(f"- RSI(14): {rsi:.1f}")
            if rsi > 70:
                content.append("- 超买区域，注意回调风险")
                bearish += 1
            elif rsi < 30:
                content.append("- 超卖区域，关注反弹机会")
                bullish += 1
            else:
                content.append("- 中性区域")
            content.append("")

        # 支撑压力位
        sr = indicators.get("support_resistance")
        if sr:
            content.append("### 支撑压力位")
            if sr.nearest_support:
                content.append(f"- 最近支撑: {sr.nearest_support:.2f} 元")
            if sr.nearest_resistance:
                content.append(f"- 最近压力: {sr.nearest_resistance:.2f} 元")
            content.append("")

        # 综合判断
        content.append("### 综合判断")
        if bullish > bearish:
            content.append("- 📈 技术面偏多")
        elif bearish > bullish:
            content.append("- 📉 技术面偏空")
        else:
            content.append("- ⚖️ 技术面中性")

        return "\n".join(content)
