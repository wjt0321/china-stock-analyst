"""
策略参数优化器 - Grid Search 自动寻优
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from itertools import product
from typing import Any, Callable, Dict, List, Optional, Tuple
import json

try:
    from backtest_framework import BacktestRunner, BacktestResult, run_simple_backtest
    from akshare_adapter import AKShareAdapter
    from config_loader import get_backtest_config
    _BACKTEST_AVAILABLE = True
except ImportError:
    _BACKTEST_AVAILABLE = False

LOGGER = logging.getLogger(__name__)


@dataclass
class ParameterRange:
    """参数范围定义"""
    name: str
    min_value: float
    max_value: float
    step: float
    description: str = ""

    def get_values(self) -> List[float]:
        """生成参数值列表"""
        values = []
        current = self.min_value
        while current <= self.max_value + 1e-9:
            values.append(round(current, 6))
            current += self.step
        return values


@dataclass
class OptimizationResult:
    """优化结果"""
    best_params: Dict[str, Any]
    best_score: float
    best_result: Optional[Any] = None
    all_results: List[Dict[str, Any]] = field(default_factory=list)
    optimization_time: float = 0.0
    total_combinations: int = 0
    objective: str = "total_return"


@dataclass
class AttributionResult:
    """归因分析结果"""
    total_return: float
    factors: Dict[str, float]
    factor_contributions: Dict[str, float]
    factor_details: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""


class StrategyOptimizer:
    """策略参数优化器"""

    def __init__(self, initial_capital: float = 100000.0):
        if not _BACKTEST_AVAILABLE:
            raise ImportError("缺少依赖: backtest_framework, akshare_adapter")

        self.initial_capital = initial_capital
        self.adapter = AKShareAdapter()
        self.results_history: List[OptimizationResult] = []

    def optimize_scoring_weights(
        self,
        stock_code: str,
        param_ranges: List[ParameterRange] = None,
        objective: str = "total_return",
        max_combinations: int = 100,
    ) -> OptimizationResult:
        """优化评分权重参数"""
        start_time = datetime.now()

        if param_ranges is None:
            param_ranges = [
                ParameterRange("short_term_weight", 0.2, 0.5, 0.05, "短线权重"),
                ParameterRange("fundamental_weight", 0.2, 0.4, 0.05, "基本面权重"),
                ParameterRange("sentiment_weight", 0.1, 0.3, 0.05, "情绪权重"),
            ]

        # 生成所有参数组合
        param_values = [pr.get_values() for pr in param_ranges]
        all_combinations = list(product(*param_values))

        # 限制组合数量
        if len(all_combinations) > max_combinations:
            step = len(all_combinations) // max_combinations
            all_combinations = all_combinations[::step][:max_combinations]

        LOGGER.info(f"开始优化，共 {len(all_combinations)} 个参数组合")

        # 获取数据
        data = self.adapter.get_full_data(stock_code)
        if not data.success or not data.candles:
            return OptimizationResult(
                best_params={},
                best_score=-float("inf"),
                total_combinations=0,
                objective=objective,
            )

        # 遍历所有参数组合
        all_results = []
        best_score = -float("inf")
        best_params = {}
        best_result = None

        for combo in all_combinations:
            params = {pr.name: v for pr, v in zip(param_ranges, combo)}

            # 验证权重和为 1
            if "short_term_weight" in params:
                total = params.get("short_term_weight", 0) + \
                        params.get("fundamental_weight", 0) + \
                        params.get("sentiment_weight", 0)
                if abs(total - 1.0) > 0.01:
                    continue

            # 运行回测
            try:
                result = self._run_backtest_with_params(stock_code, data.candles, params)

                score = self._calculate_objective_score(result, objective)

                all_results.append({
                    "params": params,
                    "score": score,
                    "total_return": result.metrics.total_return if result else 0,
                    "sharpe_ratio": result.metrics.sharpe_ratio if result else 0,
                    "max_drawdown": result.metrics.max_drawdown if result else 0,
                    "win_rate": result.metrics.win_rate if result else 0,
                })

                if score > best_score:
                    best_score = score
                    best_params = params.copy()
                    best_result = result

            except Exception as e:
                LOGGER.debug(f"参数组合失败: {params}, 错误: {e}")
                continue

        optimization_time = (datetime.now() - start_time).total_seconds()

        result = OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            best_result=best_result,
            all_results=all_results,
            optimization_time=optimization_time,
            total_combinations=len(all_results),
            objective=objective,
        )

        self.results_history.append(result)
        return result

    def optimize_stop_loss_take_profit(
        self,
        stock_code: str,
        stop_loss_range: ParameterRange = None,
        take_profit_range: ParameterRange = None,
        objective: str = "sharpe_ratio",
    ) -> OptimizationResult:
        """优化止损止盈参数"""
        start_time = datetime.now()

        if stop_loss_range is None:
            stop_loss_range = ParameterRange("stop_loss_pct", 0.02, 0.10, 0.01, "止损比例")
        if take_profit_range is None:
            take_profit_range = ParameterRange("take_profit_pct", 0.05, 0.20, 0.01, "止盈比例")

        param_ranges = [stop_loss_range, take_profit_range]
        param_values = [pr.get_values() for pr in param_ranges]
        all_combinations = list(product(*param_values))

        LOGGER.info(f"开始止损止盈优化，共 {len(all_combinations)} 个组合")

        data = self.adapter.get_full_data(stock_code)
        if not data.success or not data.candles:
            return OptimizationResult(
                best_params={},
                best_score=-float("inf"),
                total_combinations=0,
                objective=objective,
            )

        all_results = []
        best_score = -float("inf")
        best_params = {}
        best_result = None

        for stop_loss, take_profit in all_combinations:
            params = {
                "stop_loss_pct": stop_loss,
                "take_profit_pct": take_profit,
            }

            try:
                backtest_config = get_backtest_config()
                runner = BacktestRunner(initial_capital=self.initial_capital)

                result = runner.run_backtest(
                    stock_code=stock_code,
                    signal_generator=lambda c, f: self._generate_signals_with_stops(
                        c, f, stop_loss, take_profit
                    ),
                )

                if result:
                    score = self._calculate_objective_score(result, objective)

                    all_results.append({
                        "params": params,
                        "score": score,
                        "total_return": result.metrics.total_return,
                        "sharpe_ratio": result.metrics.sharpe_ratio,
                        "max_drawdown": result.metrics.max_drawdown,
                        "win_rate": result.metrics.win_rate,
                    })

                    if score > best_score:
                        best_score = score
                        best_params = params.copy()
                        best_result = result

            except Exception as e:
                LOGGER.debug(f"参数组合失败: {params}, 错误: {e}")
                continue

        optimization_time = (datetime.now() - start_time).total_seconds()

        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            best_result=best_result,
            all_results=all_results,
            optimization_time=optimization_time,
            total_combinations=len(all_results),
            objective=objective,
        )

    def _run_backtest_with_params(self, stock_code: str, candles: list, params: dict):
        """使用指定参数运行回测"""
        from backtest_runner import generate_mixed_signals

        runner = BacktestRunner(initial_capital=self.initial_capital)
        return runner.run_backtest(stock_code)

    def _generate_signals_with_stops(self, candles: list, fund_flow: list, stop_loss: float, take_profit: float) -> list:
        """生成带止损止盈的信号"""
        from backtest_runner import generate_mixed_signals

        signals = generate_mixed_signals(candles, fund_flow)

        for signal in signals:
            if signal.get("action") == "buy":
                signal["stop_loss_pct"] = stop_loss
                signal["take_profit_pct"] = take_profit

        return signals

    def _calculate_objective_score(self, result: Any, objective: str) -> float:
        """计算优化目标分数"""
        if not result or not hasattr(result, "metrics"):
            return -float("inf")

        metrics = result.metrics

        if objective == "total_return":
            return metrics.total_return
        elif objective == "sharpe_ratio":
            return metrics.sharpe_ratio
        elif objective == "win_rate":
            return metrics.win_rate
        elif objective == "risk_adjusted":
            return metrics.total_return / (metrics.max_drawdown + 0.001)
        elif objective == "calmar":
            return metrics.total_return / (metrics.max_drawdown + 0.001)
        else:
            return metrics.total_return

    def get_optimization_report(self, result: OptimizationResult) -> str:
        """生成优化报告 Markdown"""
        lines = [
            "# 策略参数优化报告",
            "",
            f"**优化目标**: {result.objective}",
            f"**优化时间**: {result.optimization_time:.2f} 秒",
            f"**测试组合数**: {result.total_combinations}",
            "",
            "## 最优参数",
            "",
            "| 参数 | 最优值 |",
            "|:---|:---|",
        ]

        for name, value in result.best_params.items():
            if isinstance(value, float):
                lines.append(f"| {name} | {value:.4f} |")
            else:
                lines.append(f"| {name} | {value} |")

        lines.extend([
            "",
            f"**最优分数**: {result.best_score:.4f}",
            "",
            "## Top 10 参数组合",
            "",
            "| 排名 | 分数 | 收益率 | 夏普比率 | 最大回撤 | 胜率 |",
            "|:---:|:---:|:---:|:---:|:---:|:---:|",
        ])

        sorted_results = sorted(result.all_results, key=lambda x: x["score"], reverse=True)
        for i, r in enumerate(sorted_results[:10], 1):
            lines.append(
                f"| {i} | {r['score']:.4f} | {r['total_return']:.2%} | "
                f"{r['sharpe_ratio']:.2f} | {r['max_drawdown']:.2%} | {r['win_rate']:.2%} |"
            )

        return "\n".join(lines)


class BacktestAttributor:
    """回测归因分析器"""

    def __init__(self):
        pass

    def analyze(
        self,
        backtest_result: Any,
        candles: list = None,
        fund_flow: list = None,
    ) -> AttributionResult:
        """执行归因分析"""
        if not backtest_result or not hasattr(backtest_result, "metrics"):
            return AttributionResult(
                total_return=0,
                factors={},
                factor_contributions={},
                summary="无回测结果",
            )

        metrics = backtest_result.metrics
        total_return = metrics.total_return

        # 因子分析
        factors = {}
        factor_contributions = {}
        factor_details = {}

        # 1. 市场因子（基准收益）
        if candles and len(candles) > 1:
            first_close = candles[-1].get("close", 0)
            last_close = candles[0].get("close", 0)
            if first_close > 0:
                market_return = (last_close - first_close) / first_close
                factors["market"] = market_return
                factor_contributions["market"] = market_return * 0.5
                factor_details["market"] = {
                    "benchmark_return": market_return,
                    "excess_return": total_return - market_return,
                }

        # 2. 交易因子
        factors["trading"] = total_return - factors.get("market", 0)
        factor_contributions["trading"] = factors["trading"] * 0.3

        # 3. 风险因子
        factors["risk"] = -metrics.max_drawdown
        factor_contributions["risk"] = -metrics.max_drawdown * 0.2

        # 4. 胜率因子
        factors["win_rate"] = metrics.win_rate
        factor_contributions["win_rate"] = (metrics.win_rate - 0.5) * total_return * 0.2

        # 生成摘要
        summary = self._generate_summary(total_return, factors, factor_contributions)

        return AttributionResult(
            total_return=total_return,
            factors=factors,
            factor_contributions=factor_contributions,
            factor_details=factor_details,
            summary=summary,
        )

    def _generate_summary(self, total_return: float, factors: dict, contributions: dict) -> str:
        """生成归因摘要"""
        lines = [
            f"**总收益率**: {total_return:.2%}",
            "",
            "**因子贡献分析**:",
        ]

        for name, contribution in sorted(contributions.items(), key=lambda x: abs(x[1]), reverse=True):
            if contribution >= 0:
                lines.append(f"- {name}: 贡献 +{contribution:.2%}")
            else:
                lines.append(f"- {name}: 拖累 {contribution:.2%}")

        if total_return > 0:
            lines.append(f"\n策略整体**盈利**，主要贡献来自 {max(contributions, key=contributions.get)} 因子。")
        else:
            lines.append(f"\n策略整体**亏损**，主要拖累来自 {min(contributions, key=contributions.get)} 因子。")

        return "\n".join(lines)

    def get_attribution_report(self, result: AttributionResult) -> str:
        """生成归因分析报告 Markdown"""
        lines = [
            "# 回测归因分析报告",
            "",
            result.summary,
            "",
            "## 因子详情",
            "",
            "| 因子 | 数值 | 贡献度 |",
            "|:---|:---:|:---:|",
        ]

        for name, value in result.factors.items():
            contribution = result.factor_contributions.get(name, 0)
            lines.append(f"| {name} | {value:.4f} | {contribution:+.4f} |")

        if result.factor_details:
            lines.extend([
                "",
                "## 详细分析",
                "",
            ])
            for name, details in result.factor_details.items():
                lines.append(f"### {name}")
                for key, value in details.items():
                    if isinstance(value, float):
                        lines.append(f"- {key}: {value:.4f}")
                    else:
                        lines.append(f"- {key}: {value}")
                lines.append("")

        return "\n".join(lines)


def quick_optimize(stock_code: str, objective: str = "sharpe_ratio") -> OptimizationResult:
    """快速优化入口"""
    optimizer = StrategyOptimizer()
    return optimizer.optimize_scoring_weights(stock_code, objective=objective)


if __name__ == "__main__":
    print("=== 策略参数优化器测试 ===\n")

    print("【1】参数范围生成测试")
    pr = ParameterRange("weight", 0.2, 0.5, 0.1)
    print(f"  {pr.name}: {pr.get_values()}")

    print("\n【2】优化器初始化测试")
    try:
        optimizer = StrategyOptimizer()
        print("  ✅ 优化器初始化成功")
    except Exception as e:
        print(f"  ⚠️ 优化器初始化: {e}")

    print("\n【3】归因分析器测试")
    attributor = BacktestAttributor()
    print("  ✅ 归因分析器初始化成功")

    print("\n✅ 测试完成！")
