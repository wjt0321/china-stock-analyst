"""Proxy fund-flow estimation from OHLCV candles.

Because true fund-flow APIs (Eastmoney) are frequently blocked or rate-limited
in this environment, we derive a deterministic buying/selling pressure signal
from the K-line itself using the midpoint tick rule:

- A candle whose close is at or above the midpoint of [low, high] is treated
  as buyer-initiated (estimate of buy-side turnover for that day).
- A candle whose close is below the midpoint is treated as seller-initiated.

This is a **proxy**, not actual exchange-reported fund flow. It is useful for
ranking relative pressure over recent sessions and is fully transparent:
anyone can reproduce it from the same OHLCV data.
"""

from typing import Any


def calc_proxy_fund_flow(candles: list[dict[str, Any]], recent_days: int = 5) -> dict:
    """Return a fund-flow-style summary derived from OHLCV.

    Args:
        candles: List of OHLCV dicts (oldest first) with at least
                 date, open, high, low, close, volume.
        recent_days: Number of recent sessions to highlight.

    Returns:
        {
            "net_flow": estimated net amount over all candles,
            "inflow_days": count of buyer-initiated days,
            "outflow_days": count of seller-initiated days,
            "recent_net_flow": net amount over recent_days,
            "recent_turnover": turnover over recent_days,
            "recent_net_pct": recent_net_flow / recent_turnover as %,
            "avg_daily_flow": net_flow / number of days,
            "direction": "inflow" | "outflow" | "neutral",
            "intensity": "strong" | "moderate" | "weak",
            "summary": human-readable Chinese summary,
        }
    """
    if not candles:
        return _empty_result()

    total_net = 0.0
    total_turnover = 0.0
    inflow_days = 0
    outflow_days = 0

    daily_flows: list[tuple[str, float, float]] = []  # (date, flow, turnover)

    for c in candles:
        close = float(c.get("close", 0))
        high = float(c.get("high", close))
        low = float(c.get("low", close))
        volume = float(c.get("volume", 0))
        date = str(c.get("date", ""))

        if close <= 0 or volume <= 0:
            continue

        turnover = close * volume
        midpoint = (high + low) / 2.0 if high != low else close
        # Buyer-initiated if close at or above midpoint.
        flow = turnover if close >= midpoint else -turnover

        total_net += flow
        total_turnover += turnover
        if flow >= 0:
            inflow_days += 1
        else:
            outflow_days += 1
        daily_flows.append((date, flow, turnover))

    recent_flows = daily_flows[-recent_days:] if len(daily_flows) >= recent_days else daily_flows
    recent_net = sum(f for _, f, _ in recent_flows)
    recent_turnover = sum(t for _, _, t in recent_flows)
    recent_net_pct = (recent_net / recent_turnover * 100) if recent_turnover > 0 else 0.0

    avg_daily = total_net / len(daily_flows) if daily_flows else 0.0

    direction = "neutral"
    if recent_net_pct > 1.0:
        direction = "inflow"
    elif recent_net_pct < -1.0:
        direction = "outflow"

    intensity = "weak"
    if abs(recent_net_pct) > 10.0:
        intensity = "strong"
    elif abs(recent_net_pct) > 3.0:
        intensity = "moderate"

    summary = _build_summary(
        recent_days, recent_net, recent_turnover, recent_net_pct, direction, intensity
    )

    return {
        "net_flow": round(total_net, 2),
        "inflow_days": inflow_days,
        "outflow_days": outflow_days,
        "recent_net_flow": round(recent_net, 2),
        "recent_turnover": round(recent_turnover, 2),
        "recent_net_pct": round(recent_net_pct, 2),
        "avg_daily_flow": round(avg_daily, 2),
        "direction": direction,
        "intensity": intensity,
        "summary": summary,
    }


def _empty_result() -> dict:
    return {
        "net_flow": 0.0,
        "inflow_days": 0,
        "outflow_days": 0,
        "recent_net_flow": 0.0,
        "recent_turnover": 0.0,
        "recent_net_pct": 0.0,
        "avg_daily_flow": 0.0,
        "direction": "neutral",
        "intensity": "weak",
        "summary": "无有效K线数据，无法估算资金流向",
    }


def _build_summary(
    recent_days: int,
    recent_net: float,
    recent_turnover: float,
    recent_net_pct: float,
    direction: str,
    intensity: str,
) -> str:
    if recent_turnover <= 0:
        return "近期无成交数据"

    dir_cn = "流入" if direction == "inflow" else "流出" if direction == "outflow" else "平衡"
    intensity_cn = {"strong": "明显", "moderate": "温和", "weak": "微弱"}.get(intensity, "")

    unit = 1e8  # 亿
    net_abs = abs(recent_net)
    unit_label = "亿" if net_abs >= unit else "万"
    unit_value = net_abs / unit if net_abs >= unit else net_abs / 1e4

    return (
        f"近{recent_days}日估算资金{intensity_cn}{dir_cn} "
        f"{unit_value:.2f}{unit_label}（占同期成交额 {recent_net_pct:.2f}%）"
    )
