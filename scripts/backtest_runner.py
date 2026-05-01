from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional
import logging

try:
    from akshare_adapter import AKShareAdapter, AKShareData, format_fund_flow_summary
    from backtest_framework import (
        BacktestRunner,
        BacktestResult,
        SignalType,
        run_simple_backtest,
    )
    from technical_indicators import calc_full_indicators, calc_atr, calc_vwap
    from config_loader import get_akshare_config, get_backtest_config
    _DEPENDENCIES_AVAILABLE = True
except ImportError:
    _DEPENDENCIES_AVAILABLE = False

LOGGER = logging.getLogger(__name__)


@dataclass
class BacktestSignal:
    date: str
    action: str
    reason: str
    confidence: float = 0.5


def generate_signals_from_indicators(candles: list) -> list:
    if not candles or len(candles) < 15:
        return []

    signals = []
    indicators = calc_full_indicators(candles)

    if not indicators:
        return []

    atr = indicators.get("atr")
    vwap = indicators.get("vwap")
    rsi = indicators.get("rsi", 50)
    volume_ratio = indicators.get("volume_ratio", 1.0)
    momentum = indicators.get("momentum", 0)
    sr = indicators.get("support_resistance")

    first_candle = candles[0]
    last_candle = candles[-1]

    buy_reasons = []
    sell_reasons = []

    if vwap and vwap.deviation_pct < -2:
        buy_reasons.append(f"VWAP偏离{abs(vwap.deviation_pct):.1f}%")
    elif vwap and vwap.deviation_pct > 3:
        sell_reasons.append(f"VWAP偏离{vwap.deviation_pct:.1f}%")

    if rsi < 30:
        buy_reasons.append(f"RSI超卖({rsi:.0f})")
    elif rsi > 70:
        sell_reasons.append(f"RSI超买({rsi:.0f})")

    if volume_ratio > 1.5:
        buy_reasons.append(f"放量{volume_ratio:.1f}倍")

    if momentum > 5:
        buy_reasons.append(f"动量+{momentum:.1f}%")
    elif momentum < -5:
        sell_reasons.append(f"动量{momentum:.1f}%")

    if sr and sr.nearest_support:
        current_price = last_candle.get("close", 0)
        support_distance = (current_price - sr.nearest_support) / current_price * 100
        if support_distance < 3:
            buy_reasons.append(f"接近支撑位{sr.nearest_support:.2f}")

    if buy_reasons:
        signals.append({
            "date": first_candle.get("date", ""),
            "action": "buy",
            "reason": "; ".join(buy_reasons),
            "confidence": min(0.9, 0.5 + len(buy_reasons) * 0.1),
        })

    if sell_reasons and len(candles) > 5:
        sell_date = candles[min(5, len(candles) - 1)].get("date", "")
        signals.append({
            "date": sell_date,
            "action": "sell",
            "reason": "; ".join(sell_reasons),
            "confidence": min(0.9, 0.5 + len(sell_reasons) * 0.1),
        })

    return signals


def generate_signals_from_fund_flow(fund_flow: list, candles: list) -> list:
    if not fund_flow or not candles:
        return []

    signals = []
    summary = format_fund_flow_summary(fund_flow, days=5)

    if not summary:
        return []

    direction = summary.get("direction", "")
    intensity = summary.get("intensity", "")
    total_net = summary.get("total_net", 0)

    first_candle = candles[0]

    if direction == "流入" and intensity in ["强势", "温和"]:
        signals.append({
            "date": first_candle.get("date", ""),
            "action": "buy",
            "reason": f"主力{intensity}{direction} {abs(total_net)/1e8:.2f}亿",
            "confidence": 0.7 if intensity == "强势" else 0.6,
        })

    return signals


def generate_mixed_signals(candles: list, fund_flow: list) -> list:
    indicator_signals = generate_signals_from_indicators(candles)
    fund_signals = generate_signals_from_fund_flow(fund_flow, candles)

    all_signals = indicator_signals + fund_signals

    if not all_signals:
        if candles:
            all_signals.append({
                "date": candles[0].get("date", ""),
                "action": "buy",
                "reason": "默认入场",
                "confidence": 0.5,
            })

    return all_signals


class AKShareBacktestRunner:
    def __init__(self, initial_capital: float = None):
        if not _DEPENDENCIES_AVAILABLE:
            raise ImportError("缺少依赖: akshare_adapter, backtest_framework, technical_indicators")

        backtest_config = get_backtest_config()
        self.initial_capital = initial_capital or backtest_config.get("default_initial_capital", 100000.0)
        self.adapter = AKShareAdapter()

    def run_backtest(
        self,
        stock_code: str,
        signal_generator: Callable = None,
        history_days: int = None,
    ) -> BacktestResult:
        akshare_config = get_akshare_config()
        history_days = history_days or akshare_config.get("default_history_days", 60)

        data = self.adapter.get_full_data(stock_code)

        if not data.success:
            LOGGER.error(f"获取数据失败: {data.error_message}")
            return None

        candles = data.candles
        fund_flow = data.fund_flow

        if not candles:
            LOGGER.error(f"无K线数据: {stock_code}")
            return None

        if signal_generator is None:
            signal_generator = generate_mixed_signals

        signals = signal_generator(candles, fund_flow)

        result = run_simple_backtest(
            stock_code=stock_code,
            candles=candles,
            signals=signals,
            initial_capital=self.initial_capital,
        )

        result.stock_name = data.stock_name

        return result

    def run_multi_stock_backtest(
        self,
        stock_codes: list,
        signal_generator: Callable = None,
    ) -> dict:
        results = {}

        for code in stock_codes:
            try:
                result = self.run_backtest(code, signal_generator)
                if result:
                    results[code] = result
            except Exception as e:
                LOGGER.error(f"回测失败 {code}: {e}")

        return results

    def compare_stocks(
        self,
        stock_codes: list,
        signal_generator: Callable = None,
    ) -> dict:
        results = self.run_multi_stock_backtest(stock_codes, signal_generator)

        comparison = {
            "stocks": [],
            "best_return": None,
            "best_stock": None,
            "summary": "",
        }

        for code, result in results.items():
            stock_info = {
                "code": code,
                "name": result.stock_name,
                "total_return": result.metrics.total_return,
                "win_rate": result.metrics.win_rate,
                "max_drawdown": result.metrics.max_drawdown,
                "sharpe_ratio": result.metrics.sharpe_ratio,
            }
            comparison["stocks"].append(stock_info)

        if comparison["stocks"]:
            comparison["stocks"].sort(key=lambda x: x["total_return"], reverse=True)
            comparison["best_stock"] = comparison["stocks"][0]
            comparison["best_return"] = comparison["best_stock"]["total_return"]

            best = comparison["best_stock"]
            comparison["summary"] = (
                f"最优标的: {best['code']} {best['name']} "
                f"收益率 {best['total_return']:.2%} "
                f"胜率 {best['win_rate']:.2%}"
            )

        return comparison


def quick_backtest(stock_code: str, initial_capital: float = 100000.0) -> BacktestResult:
    runner = AKShareBacktestRunner(initial_capital=initial_capital)
    return runner.run_backtest(stock_code)


if __name__ == "__main__":
    print("=== AKShare 回测集成测试 ===\n")

    runner = AKShareBacktestRunner(initial_capital=100000.0)

    print("【1】单股回测: 600519 贵州茅台")
    result = runner.run_backtest("600519")

    if result:
        print(f"  股票: {result.stock_code} {result.stock_name}")
        print(f"  总收益: {result.metrics.total_return:.2%}")
        print(f"  最大回撤: {result.metrics.max_drawdown:.2%}")
        print(f"  胜率: {result.metrics.win_rate:.2%}")
        print(f"  夏普比率: {result.metrics.sharpe_ratio:.2f}")
        print(f"  交易次数: {result.metrics.total_trades}")
    else:
        print("  回测失败")

    print("\n【2】信号生成测试")
    data = runner.adapter.get_full_data("600519")
    signals = generate_mixed_signals(data.candles, data.fund_flow)
    print(f"  生成信号: {len(signals)} 个")
    for s in signals[:3]:
        print(f"  - {s['date']}: {s['action']} ({s['reason'][:30]}...)")

    print("\n【3】多股对比回测")
    comparison = runner.compare_stocks(["600519", "000858"])
    print(f"  {comparison.get('summary', '无结果')}")

    print("\n✅ 测试完成！")
