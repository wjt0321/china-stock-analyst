from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import logging

try:
    from technical_indicators import (
        calc_full_indicators,
        calc_atr,
        calc_vwap,
        calc_rsi,
        calc_support_resistance_levels,
        calc_volume_ratio,
        calc_momentum,
        ATRResult,
        VWAPResult,
        SupportResistance,
    )
    from config_loader import get_technical_indicators_config
    _INDICATORS_AVAILABLE = True
except ImportError:
    _INDICATORS_AVAILABLE = False

LOGGER = logging.getLogger(__name__)


@dataclass
class TechnicalReportSection:
    title: str
    content: str
    signals: list
    confidence: float


def format_price(price: float) -> str:
    if price >= 100:
        return f"{price:.2f}"
    elif price >= 10:
        return f"{price:.2f}"
    else:
        return f"{price:.3f}"


def generate_atr_section(atr_result, current_price: float) -> TechnicalReportSection:
    if not atr_result or atr_result.atr <= 0:
        return TechnicalReportSection(
            title="ATR 波动率",
            content="数据不足，无法计算ATR",
            signals=[],
            confidence=0.0,
        )

    config = {}
    if _INDICATORS_AVAILABLE:
        config = get_technical_indicators_config()
    stop_multiplier = config.get("stop_loss_multiplier", 2.0)

    atr = atr_result.atr
    atr_pct = (atr / current_price) * 100 if current_price > 0 else 0
    stop_loss = current_price - (atr * stop_multiplier)
    stop_loss_pct = (stop_multiplier * atr_pct)

    volatility_level = "低"
    if atr_pct > 3:
        volatility_level = "高"
    elif atr_pct > 1.5:
        volatility_level = "中"

    signals = []
    if atr_pct > 3:
        signals.append({"type": "warning", "message": f"波动率较高({atr_pct:.1f}%)，注意风险控制"})
    elif atr_pct < 1:
        signals.append({"type": "info", "message": f"波动率较低({atr_pct:.1f}%)，可能面临变盘"})

    content = f"""
| 指标 | 数值 |
|:---|:---|
| ATR(14) | {format_price(atr)} 元 |
| ATR占比 | {atr_pct:.2f}% |
| 波动水平 | {volatility_level} |
| 建议止损 | {format_price(stop_loss)} 元 (-{stop_loss_pct:.1f}%) |
""".strip()

    return TechnicalReportSection(
        title="ATR 波动率分析",
        content=content,
        signals=signals,
        confidence=0.8 if atr_pct > 0 else 0.5,
    )


def generate_vwap_section(vwap_result, current_price: float) -> TechnicalReportSection:
    if not vwap_result or vwap_result.vwap <= 0:
        return TechnicalReportSection(
            title="VWAP 成交量加权均价",
            content="数据不足，无法计算VWAP",
            signals=[],
            confidence=0.0,
        )

    vwap = vwap_result.vwap
    deviation = vwap_result.deviation
    deviation_pct = vwap_result.deviation_pct

    signals = []
    if deviation_pct > 3:
        signals.append({"type": "warning", "message": f"价格高于VWAP {deviation_pct:.1f}%，可能回调"})
    elif deviation_pct < -3:
        signals.append({"type": "bullish", "message": f"价格低于VWAP {abs(deviation_pct):.1f}%，存在反弹空间"})

    position = "上方" if deviation > 0 else "下方"
    bias = "偏多" if deviation > 0 else "偏空"

    content = f"""
| 指标 | 数值 |
|:---|:---|
| VWAP | {format_price(vwap)} 元 |
| 当前价 | {format_price(current_price)} 元 |
| 偏离值 | {format_price(abs(deviation))} 元 |
| 偏离度 | {deviation_pct:+.2f}% |
| 位置判断 | 价格位于VWAP{position}({bias}) |
""".strip()

    return TechnicalReportSection(
        title="VWAP 分析",
        content=content,
        signals=signals,
        confidence=0.7,
    )


def generate_rsi_section(rsi: float) -> TechnicalReportSection:
    if rsi is None:
        return TechnicalReportSection(
            title="RSI 相对强弱指标",
            content="数据不足，无法计算RSI",
            signals=[],
            confidence=0.0,
        )

    signals = []
    zone = "中性"
    if rsi > 80:
        zone = "严重超买"
        signals.append({"type": "warning", "message": f"RSI={rsi:.0f}，严重超买，回调风险高"})
    elif rsi > 70:
        zone = "超买"
        signals.append({"type": "warning", "message": f"RSI={rsi:.0f}，超买区域，注意回调"})
    elif rsi < 20:
        zone = "严重超卖"
        signals.append({"type": "bullish", "message": f"RSI={rsi:.0f}，严重超卖，反弹概率大"})
    elif rsi < 30:
        zone = "超卖"
        signals.append({"type": "bullish", "message": f"RSI={rsi:.0f}，超卖区域，关注反弹"})

    content = f"""
| 指标 | 数值 |
|:---|:---|
| RSI(14) | {rsi:.1f} |
| 区域 | {zone} |
""".strip()

    return TechnicalReportSection(
        title="RSI 分析",
        content=content,
        signals=signals,
        confidence=0.75,
    )


def generate_support_resistance_section(sr_result, current_price: float) -> TechnicalReportSection:
    if not sr_result:
        return TechnicalReportSection(
            title="支撑压力位",
            content="数据不足，无法计算支撑压力位",
            signals=[],
            confidence=0.0,
        )

    signals = []

    nearest_support = sr_result.nearest_support
    nearest_resistance = sr_result.nearest_resistance

    if nearest_support:
        support_distance = ((current_price - nearest_support) / current_price) * 100
        if support_distance < 3:
            signals.append({"type": "info", "message": f"接近支撑位 {format_price(nearest_support)} 元"})

    if nearest_resistance:
        resistance_distance = ((nearest_resistance - current_price) / current_price) * 100
        if resistance_distance < 3:
            signals.append({"type": "warning", "message": f"接近压力位 {format_price(nearest_resistance)} 元"})

    support_levels = sr_result.support_levels or []
    resistance_levels = sr_result.resistance_levels or []

    support_str = "、".join([format_price(s) for s in support_levels[:3]]) if support_levels else "无"
    resistance_str = "、".join([format_price(r) for r in resistance_levels[:3]]) if resistance_levels else "无"

    content = f"""
| 指标 | 数值 |
|:---|:---|
| 当前价 | {format_price(current_price)} 元 |
| 最近支撑 | {format_price(nearest_support) if nearest_support else '无'} |
| 最近压力 | {format_price(nearest_resistance) if nearest_resistance else '无'} |
| 支撑位 | {support_str} |
| 压力位 | {resistance_str} |
""".strip()

    return TechnicalReportSection(
        title="支撑压力位分析",
        content=content,
        signals=signals,
        confidence=0.7,
    )


def generate_volume_ratio_section(volume_ratio: float) -> TechnicalReportSection:
    if volume_ratio is None:
        return TechnicalReportSection(
            title="量比分析",
            content="数据不足，无法计算量比",
            signals=[],
            confidence=0.0,
        )

    signals = []
    status = "正常"

    if volume_ratio > 2.5:
        status = "异常放量"
        signals.append({"type": "warning", "message": f"量比{volume_ratio:.1f}倍，异常放量，关注主力动向"})
    elif volume_ratio > 1.5:
        status = "放量"
        signals.append({"type": "info", "message": f"量比{volume_ratio:.1f}倍，成交量放大"})
    elif volume_ratio < 0.5:
        status = "缩量"
        signals.append({"type": "info", "message": f"量比{volume_ratio:.1f}倍，成交量萎缩"})

    content = f"""
| 指标 | 数值 |
|:---|:---|
| 量比 | {volume_ratio:.2f} |
| 状态 | {status} |
""".strip()

    return TechnicalReportSection(
        title="量比分析",
        content=content,
        signals=signals,
        confidence=0.65,
    )


def generate_momentum_section(momentum: float) -> TechnicalReportSection:
    if momentum is None:
        return TechnicalReportSection(
            title="动量分析",
            content="数据不足，无法计算动量",
            signals=[],
            confidence=0.0,
        )

    signals = []
    trend = "震荡"

    if momentum > 10:
        trend = "强势上涨"
        signals.append({"type": "bullish", "message": f"动量+{momentum:.1f}%，强势上涨趋势"})
    elif momentum > 5:
        trend = "上涨"
        signals.append({"type": "bullish", "message": f"动量+{momentum:.1f}%，上涨趋势"})
    elif momentum < -10:
        trend = "强势下跌"
        signals.append({"type": "warning", "message": f"动量{momentum:.1f}%，强势下跌趋势"})
    elif momentum < -5:
        trend = "下跌"
        signals.append({"type": "warning", "message": f"动量{momentum:.1f}%，下跌趋势"})

    content = f"""
| 指标 | 数值 |
|:---|:---|
| 动量(10日) | {momentum:+.2f}% |
| 趋势 | {trend} |
""".strip()

    return TechnicalReportSection(
        title="动量分析",
        content=content,
        signals=signals,
        confidence=0.7,
    )


def generate_technical_report(candles: list) -> dict:
    if not candles or not _INDICATORS_AVAILABLE:
        return {
            "success": False,
            "sections": [],
            "summary": "数据不足或模块不可用",
            "signals": [],
        }

    indicators = calc_full_indicators(candles)

    if not indicators:
        return {
            "success": False,
            "sections": [],
            "summary": "无法计算技术指标",
            "signals": [],
        }

    current_price = indicators.get("price", 0)

    sections = []

    atr_section = generate_atr_section(indicators.get("atr"), current_price)
    sections.append(atr_section)

    vwap_section = generate_vwap_section(indicators.get("vwap"), current_price)
    sections.append(vwap_section)

    rsi_section = generate_rsi_section(indicators.get("rsi"))
    sections.append(rsi_section)

    sr_section = generate_support_resistance_section(indicators.get("support_resistance"), current_price)
    sections.append(sr_section)

    volume_section = generate_volume_ratio_section(indicators.get("volume_ratio"))
    sections.append(volume_section)

    momentum_section = generate_momentum_section(indicators.get("momentum"))
    sections.append(momentum_section)

    all_signals = []
    for section in sections:
        all_signals.extend(section.signals)

    bullish_count = sum(1 for s in all_signals if s.get("type") == "bullish")
    warning_count = sum(1 for s in all_signals if s.get("type") == "warning")

    if bullish_count > warning_count + 1:
        overall = "偏多"
    elif warning_count > bullish_count + 1:
        overall = "偏空"
    else:
        overall = "中性"

    summary = f"技术面综合判断: {overall}，共{len(all_signals)}个信号"

    return {
        "success": True,
        "sections": sections,
        "summary": summary,
        "signals": all_signals,
        "overall": overall,
        "indicators": {
            "price": current_price,
            "atr": indicators.get("atr").atr if indicators.get("atr") else None,
            "vwap": indicators.get("vwap").vwap if indicators.get("vwap") else None,
            "rsi": indicators.get("rsi"),
            "volume_ratio": indicators.get("volume_ratio"),
            "momentum": indicators.get("momentum"),
        },
    }


def render_technical_report_markdown(candles: list) -> str:
    report = generate_technical_report(candles)

    if not report.get("success"):
        return f"## 技术分析\n\n{report.get('summary', '无法生成报告')}"

    lines = ["## 技术分析", ""]

    for section in report.get("sections", []):
        lines.append(f"### {section.title}")
        lines.append("")
        lines.append(section.content)
        lines.append("")

        if section.signals:
            lines.append("**信号:**")
            for signal in section.signals:
                icon = "⚠️" if signal["type"] == "warning" else "📈" if signal["type"] == "bullish" else "ℹ️"
                lines.append(f"- {icon} {signal['message']}")
            lines.append("")

    lines.append("### 综合判断")
    lines.append("")
    lines.append(f"**{report.get('summary', '')}**")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    print("=== 技术指标报告生成测试 ===\n")

    sample_candles = [
        {"date": "2026-04-01", "open": 1400.0, "high": 1420.0, "low": 1390.0, "close": 1410.0, "volume": 5000000},
        {"date": "2026-04-02", "open": 1410.0, "high": 1430.0, "low": 1405.0, "close": 1425.0, "volume": 5500000},
        {"date": "2026-04-03", "open": 1425.0, "high": 1440.0, "low": 1420.0, "close": 1435.0, "volume": 6000000},
        {"date": "2026-04-07", "open": 1435.0, "high": 1450.0, "low": 1430.0, "close": 1440.0, "volume": 5800000},
        {"date": "2026-04-08", "open": 1440.0, "high": 1455.0, "low": 1435.0, "close": 1445.0, "volume": 6200000},
        {"date": "2026-04-09", "open": 1445.0, "high": 1460.0, "low": 1440.0, "close": 1450.0, "volume": 6500000},
        {"date": "2026-04-10", "open": 1450.0, "high": 1465.0, "low": 1445.0, "close": 1455.0, "volume": 7000000},
        {"date": "2026-04-13", "open": 1455.0, "high": 1470.0, "low": 1450.0, "close": 1460.0, "volume": 6800000},
        {"date": "2026-04-14", "open": 1460.0, "high": 1475.0, "low": 1455.0, "close": 1465.0, "volume": 7200000},
        {"date": "2026-04-15", "open": 1465.0, "high": 1480.0, "low": 1460.0, "close": 1470.0, "volume": 7500000},
        {"date": "2026-04-16", "open": 1470.0, "high": 1485.0, "low": 1465.0, "close": 1475.0, "volume": 7800000},
        {"date": "2026-04-17", "open": 1475.0, "high": 1490.0, "low": 1470.0, "close": 1480.0, "volume": 8000000},
        {"date": "2026-04-20", "open": 1480.0, "high": 1495.0, "low": 1475.0, "close": 1485.0, "volume": 8200000},
        {"date": "2026-04-21", "open": 1485.0, "high": 1500.0, "low": 1480.0, "close": 1490.0, "volume": 8500000},
        {"date": "2026-04-22", "open": 1490.0, "high": 1505.0, "low": 1485.0, "close": 1495.0, "volume": 8800000},
    ]

    print(render_technical_report_markdown(sample_candles))

    print("\n✅ 测试完成！")
