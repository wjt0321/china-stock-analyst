from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import json


class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    SHORT_BUY = "short_buy"
    SHORT_SELL = "short_sell"


class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"
    CASH = "cash"


@dataclass
class Trade:
    timestamp: str
    signal: SignalType
    price: float
    quantity: float
    commission: float
    pnl: float = 0.0
    remarks: str = ""


@dataclass
class Position:
    side: PositionSide
    entry_price: float
    quantity: float
    entry_date: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class PortfolioSnapshot:
    date: str
    cash: float
    position_value: float
    total_value: float
    position: Optional[Position] = None


@dataclass
class BacktestMetrics:
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    profit_loss_ratio: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_holding_days: float
    max_consecutive_wins: int
    max_consecutive_losses: int

    def to_dict(self) -> dict:
        return {
            "total_return": f"{self.total_return:.2%}",
            "annualized_return": f"{self.annualized_return:.2%}",
            "max_drawdown": f"{self.max_drawdown:.2%}",
            "sharpe_ratio": f"{self.sharpe_ratio:.2f}",
            "win_rate": f"{self.win_rate:.2%}",
            "profit_loss_ratio": f"{self.profit_loss_ratio:.2f}",
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_holding_days": f"{self.avg_holding_days:.1f}",
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
        }


@dataclass
class BacktestResult:
    stock_code: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    trades: list
    snapshots: list
    metrics: BacktestMetrics
    signals: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "stock_code": self.stock_code,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "total_return": self.metrics.total_return,
            "annualized_return": self.metrics.annualized_return,
            "max_drawdown": self.metrics.max_drawdown,
            "sharpe_ratio": self.metrics.sharpe_ratio,
            "win_rate": self.metrics.win_rate,
            "total_trades": self.metrics.total_trades,
            "winning_trades": self.metrics.winning_trades,
            "losing_trades": self.metrics.losing_trades,
            "trades_count": len(self.trades),
        }

    def to_markdown(self) -> str:
        lines = [
            f"# {self.stock_code} 回测报告",
            "",
            f"**回测区间**: {self.start_date} ~ {self.end_date}",
            f"**初始资金**: {self.initial_capital:,.2f}",
            f"**最终资金**: {self.final_capital:,.2f}",
            "",
            "## 绩效指标",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 总收益率 | {self.metrics.total_return:.2%} |",
            f"| 年化收益率 | {self.metrics.annualized_return:.2%} |",
            f"| 最大回撤 | {self.metrics.max_drawdown:.2%} |",
            f"| 夏普比率 | {self.metrics.sharpe_ratio:.2f} |",
            f"| 胜率 | {self.metrics.win_rate:.2%} |",
            f"| 盈亏比 | {self.metrics.profit_loss_ratio:.2f} |",
            "",
            "## 交易统计",
            "",
            f"- 总交易次数: {self.metrics.total_trades}",
            f"- 盈利次数: {self.metrics.winning_trades}",
            f"- 亏损次数: {self.metrics.losing_trades}",
            f"- 平均持仓天数: {self.metrics.avg_holding_days:.1f}",
            f"| 最大连续盈利 | {self.metrics.max_consecutive_wins} |",
            f"| 最大连续亏损 | {self.metrics.max_consecutive_losses} |",
        ]

        if self.trades:
            lines.extend(["", "## 交易记录", ""])
            lines.append("| 日期 | 信号 | 价格 | 数量 | 盈亏 |")
            lines.append("|------|------|------|------|------|")
            for trade in self.trades[-20:]:
                lines.append(
                    f"| {trade.timestamp[:10]} | {trade.signal.value} | "
                    f"{trade.price:.2f} | {trade.quantity:.0f} | "
                    f"{'+' if trade.pnl >= 0 else ''}{trade.pnl:.2f} |"
                )

        return "\n".join(lines)


class BacktestRunner:
    def __init__(
        self,
        initial_capital: float = 100000.0,
        commission_rate: float = 0.0003,
        slippage: float = 0.001,
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage = slippage
        self.cash = initial_capital
        self.position: Optional[Position] = None
        self.trades: list = []
        self.snapshots: list = []
        self.equity_curve: list = []

    def reset(self):
        self.cash = self.initial_capital
        self.position = None
        self.trades = []
        self.snapshots = []
        self.equity_curve = []

    def _calc_commission(self, amount: float) -> float:
        return amount * self.commission_rate

    def _apply_slippage(self, price: float, is_buy: bool) -> float:
        factor = 1 + self.slippage if is_buy else 1 - self.slippage
        return round(price * factor, 2)

    def _get_position_value(self, current_price: float) -> float:
        if self.position is None:
            return 0.0
        return self.position.quantity * current_price

    def buy(
        self,
        date: str,
        price: float,
        quantity: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> bool:
        if self.position is not None:
            return False

        exec_price = self._apply_slippage(price, is_buy=True)
        if quantity is None:
            max_qty = self.cash / (exec_price * (1 + self.commission_rate))
            quantity = int(max_qty / 100) * 100

        cost = exec_price * quantity
        commission = self._calc_commission(cost)

        if cost + commission > self.cash:
            quantity = int(self.cash / (exec_price * (1 + self.commission_rate)) / 100) * 100
            cost = exec_price * quantity
            commission = self._calc_commission(cost)

        if quantity <= 0:
            return False

        self.cash -= (cost + commission)
        self.position = Position(
            side=PositionSide.LONG,
            entry_price=exec_price,
            quantity=quantity,
            entry_date=date,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        trade = Trade(
            timestamp=date,
            signal=SignalType.BUY,
            price=exec_price,
            quantity=quantity,
            commission=commission,
            pnl=0.0,
            remarks=f"建仓{quantity}股",
        )
        self.trades.append(trade)
        return True

    def sell(
        self,
        date: str,
        price: float,
        quantity: Optional[float] = None,
        remarks: str = "",
    ) -> bool:
        if self.position is None or self.position.side != PositionSide.LONG:
            return False

        exec_price = self._apply_slippage(price, is_buy=False)
        sell_qty = quantity if quantity else self.position.quantity

        proceeds = exec_price * sell_qty
        commission = self._calc_commission(proceeds)
        pnl = proceeds - commission - (self.position.entry_price * sell_qty)

        self.cash += (proceeds - commission)

        trade = Trade(
            timestamp=date,
            signal=SignalType.SELL,
            price=exec_price,
            quantity=sell_qty,
            commission=commission,
            pnl=pnl,
            remarks=remarks or f"平仓{quantity}股",
        )
        self.trades.append(trade)

        if sell_qty >= self.position.quantity:
            self.position = None
        else:
            self.position.quantity -= sell_qty

        return True

    def check_stop_loss(self, date: str, price: float) -> bool:
        if self.position is None or self.position.stop_loss is None:
            return False

        if price <= self.position.stop_loss:
            self.sell(date, self.position.stop_loss, remarks="止损")
            return True
        return False

    def check_take_profit(self, date: str, price: float) -> bool:
        if self.position is None or self.position.take_profit is None:
            return False

        if price >= self.position.take_profit:
            self.sell(date, self.position.take_profit, remarks="止盈")
            return True
        return False

    def snapshot(self, date: str, current_price: float) -> PortfolioSnapshot:
        position_value = self._get_position_value(current_price)
        total_value = self.cash + position_value

        snapshot = PortfolioSnapshot(
            date=date,
            cash=self.cash,
            position_value=position_value,
            total_value=total_value,
            position=self.position,
        )
        self.snapshots.append(snapshot)
        self.equity_curve.append(total_value)
        return snapshot

    def run(
        self,
        candles: list,
        signals: list,
        stock_code: str = "UNKNOWN",
        stop_loss_pct: float = 0.05,
        take_profit_pct: float = 0.10,
    ) -> BacktestResult:
        self.reset()

        start_date = candles[0].get("date", "") if candles else ""
        end_date = candles[-1].get("date", "") if candles else ""

        for i, candle in enumerate(candles):
            date = candle.get("date", "")
            current_price = float(candle.get("close", 0))

            if current_price <= 0:
                continue

            if self.position is None:
                if i < len(signals) and signals[i].get("action") == "buy":
                    sl = current_price * (1 - stop_loss_pct)
                    tp = current_price * (1 + take_profit_pct)
                    self.buy(date, current_price, stop_loss=sl, take_profit=tp)
            else:
                if self.check_stop_loss(date, current_price):
                    continue
                if self.check_take_profit(date, current_price):
                    continue
                if i < len(signals) and signals[i].get("action") == "sell":
                    self.sell(date, current_price, remarks="信号卖出")

            self.snapshot(date, current_price)

        if self.position is not None:
            final_price = candles[-1].get("close", 0) if candles else 0
            self.sell(
                candles[-1].get("date", ""),
                float(final_price),
                remarks="回测结束强制平仓"
            )

        metrics = self._calc_metrics(candles)

        return BacktestResult(
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=self.cash,
            trades=self.trades,
            snapshots=self.snapshots,
            metrics=metrics,
            signals=signals,
        )

    def _calc_metrics(self, candles: list) -> BacktestMetrics:
        if not self.equity_curve:
            return BacktestMetrics(
                total_return=0, annualized_return=0, max_drawdown=0,
                sharpe_ratio=0, win_rate=0, profit_loss_ratio=0,
                total_trades=0, winning_trades=0, losing_trades=0,
                avg_holding_days=0, max_consecutive_wins=0, max_consecutive_losses=0
            )

        total_return = (self.cash - self.initial_capital) / self.initial_capital

        if len(candles) > 1:
            days = len(candles)
            annualized_return = (1 + total_return) ** (365 / days) - 1
        else:
            annualized_return = 0

        peak = self.equity_curve[0]
        max_drawdown = 0
        for value in self.equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        returns = []
        for i in range(1, len(self.equity_curve)):
            ret = (self.equity_curve[i] - self.equity_curve[i-1]) / self.equity_curve[i-1]
            returns.append(ret)

        if returns and len(returns) > 1:
            import statistics
            avg_return = statistics.mean(returns)
            std_return = statistics.stdev(returns) if len(returns) > 1 else 0
            sharpe_ratio = (avg_return / std_return * (252 ** 0.5)) if std_return > 0 else 0
        else:
            sharpe_ratio = 0

        winning_trades = [t for t in self.trades if t.signal == SignalType.SELL and t.pnl > 0]
        losing_trades = [t for t in self.trades if t.signal == SignalType.SELL and t.pnl < 0]

        win_rate = len(winning_trades) / len(self.trades) if self.trades else 0

        if winning_trades and losing_trades:
            avg_win = statistics.mean([t.pnl for t in winning_trades])
            avg_loss = abs(statistics.mean([t.pnl for t in losing_trades]))
            profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        else:
            profit_loss_ratio = 0

        holding_days_list = []
        for t in self.trades:
            if t.signal == SignalType.SELL:
                entry = next((e for e in reversed(self.trades) if e.signal == SignalType.BUY and e.timestamp < t.timestamp), None)
                if entry:
                    d1 = datetime.strptime(entry.timestamp[:10], "%Y-%m-%d")
                    d2 = datetime.strptime(t.timestamp[:10], "%Y-%m-%d")
                    holding_days_list.append((d2 - d1).days)

        avg_holding_days = statistics.mean(holding_days_list) if holding_days_list else 0

        consecutive = 0
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        for t in self.trades:
            if t.signal == SignalType.SELL:
                if t.pnl > 0:
                    consecutive = consecutive + 1 if consecutive > 0 else 1
                    max_consecutive_wins = max(max_consecutive_wins, consecutive)
                else:
                    consecutive = consecutive - 1 if consecutive < 0 else -1
                    max_consecutive_losses = max(max_consecutive_losses, abs(consecutive))

        return BacktestMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            profit_loss_ratio=profit_loss_ratio,
            total_trades=len([t for t in self.trades if t.signal == SignalType.SELL]),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            avg_holding_days=avg_holding_days,
            max_consecutive_wins=max_consecutive_wins,
            max_consecutive_losses=max_consecutive_losses,
        )


def run_simple_backtest(
    stock_code: str,
    candles: list,
    signals: list,
    initial_capital: float = 100000.0,
) -> BacktestResult:
    runner = BacktestRunner(initial_capital=initial_capital)
    return runner.run(candles, signals, stock_code)


if __name__ == "__main__":
    sample_candles = [
        {"date": "2026-01-02", "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.3, "volume": 1000000},
        {"date": "2026-01-03", "open": 10.3, "high": 10.8, "low": 10.2, "close": 10.5, "volume": 1100000},
        {"date": "2026-01-06", "open": 10.5, "high": 11.0, "low": 10.4, "close": 10.8, "volume": 1200000},
        {"date": "2026-01-07", "open": 10.8, "high": 11.2, "low": 10.7, "close": 11.0, "volume": 1300000},
        {"date": "2026-01-08", "open": 11.0, "high": 11.5, "low": 10.9, "close": 11.2, "volume": 1400000},
        {"date": "2026-01-09", "open": 11.2, "high": 11.8, "low": 11.1, "close": 11.5, "volume": 1500000},
        {"date": "2026-01-10", "open": 11.5, "high": 12.0, "low": 11.4, "close": 11.8, "volume": 1600000},
        {"date": "2026-01-13", "open": 11.8, "high": 12.2, "low": 11.7, "close": 12.0, "volume": 1700000},
        {"date": "2026-01-14", "open": 12.0, "high": 12.5, "low": 11.9, "close": 12.3, "volume": 1800000},
        {"date": "2026-01-15", "open": 12.3, "high": 12.8, "low": 12.2, "close": 12.5, "volume": 1900000},
    ]

    sample_signals = [
        {"date": "2026-01-02", "action": "buy", "reason": "技术指标看涨"},
        {"date": "2026-01-08", "action": "sell", "reason": "止盈信号"},
    ]

    result = run_simple_backtest("600519", sample_candles, sample_signals, initial_capital=100000)

    print("=== 回测结果 ===")
    print(result.to_markdown())

    with open("backtest_result.json", "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
    print("\n已保存到 backtest_result.json")
