from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class OHLCV:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    @classmethod
    def from_dict(cls, data: dict) -> "OHLCV":
        return cls(
            date=data.get("date", ""),
            open=float(data.get("open", 0)),
            high=float(data.get("high", 0)),
            low=float(data.get("low", 0)),
            close=float(data.get("close", 0)),
            volume=float(data.get("volume", 0)),
        )


@dataclass
class ATRResult:
    atr: float
    atr_14: float
    tr_list: list
    date: str


@dataclass
class VWAPResult:
    vwap: float
    price_avg: float
    deviation: float
    deviation_pct: float
    date: str


@dataclass
class SupportResistance:
    support_levels: list
    resistance_levels: list
    nearest_support: Optional[float]
    nearest_resistance: Optional[float]


def calc_true_range(high: float, low: float, prev_close: float) -> float:
    return max(
        high - low,
        abs(high - prev_close),
        abs(low - prev_close)
    )


def calc_atr(candles: list, period: int = 14) -> ATRResult:
    if not candles or len(candles) < 2:
        return ATRResult(atr=0, atr_14=0, tr_list=[], date="")

    ohlcv_list = [OHLCV.from_dict(c) if isinstance(c, dict) else c for c in candles]

    tr_list = []
    for i, candle in enumerate(ohlcv_list):
        if i == 0:
            tr = candle.high - candle.low
        else:
            tr = calc_true_range(candle.high, candle.low, ohlcv_list[i-1].close)
        tr_list.append(round(tr, 4))

    if len(tr_list) < period:
        atr = sum(tr_list) / len(tr_list) if tr_list else 0
    else:
        sma_start = sum(tr_list[:period])
        atr = sma_start
        for i in range(period, len(tr_list)):
            atr = (atr * (period - 1) + tr_list[i]) / period

    atr_14 = atr

    return ATRResult(
        atr=round(atr, 4),
        atr_14=round(atr_14, 4),
        tr_list=tr_list,
        date=ohlcv_list[-1].date
    )


def calc_vwap(candles: list) -> VWAPResult:
    if not candles:
        return VWAPResult(vwap=0, price_avg=0, deviation=0, deviation_pct=0, date="")

    ohlcv_list = [OHLCV.from_dict(c) if isinstance(c, dict) else c for c in candles]

    total_pv = sum(c.close * c.volume for c in ohlcv_list)
    total_vol = sum(c.volume for c in ohlcv_list)

    if total_vol == 0:
        return VWAPResult(vwap=0, price_avg=0, deviation=0, deviation_pct=0, date="")

    vwap = total_pv / total_vol
    price_avg = sum(c.close for c in ohlcv_list) / len(ohlcv_list)

    current_price = ohlcv_list[-1].close
    deviation = current_price - vwap
    deviation_pct = (deviation / vwap * 100) if vwap != 0 else 0

    return VWAPResult(
        vwap=round(vwap, 4),
        price_avg=round(price_avg, 4),
        deviation=round(deviation, 4),
        deviation_pct=round(deviation_pct, 2),
        date=ohlcv_list[-1].date
    )


def calc_atr_stop_loss(current_price: float, atr: float, multiplier: float = 2.0) -> dict:
    stop_loss = current_price - (atr * multiplier)
    return {
        "stop_loss": round(stop_loss, 2),
        "entry_price": current_price,
        "risk_amount": round(atr * multiplier, 2),
        "risk_pct": round((atr * multiplier / current_price) * 100, 2)
    }


def calc_support_resistance_levels(candles: list, lookback: int = 20, tolerance: float = 0.01) -> SupportResistance:
    if not candles or len(candles) < 3:
        return SupportResistance(
            support_levels=[],
            resistance_levels=[],
            nearest_support=None,
            nearest_resistance=None
        )

    ohlcv_list = [OHLCV.from_dict(c) if isinstance(c, dict) else c for c in candles[-lookback:]]

    highs = [c.high for c in ohlcv_list]
    lows = [c.low for c in ohlcv_list]

    local_highs = []
    local_lows = []

    for i in range(1, len(ohlcv_list) - 1):
        if ohlcv_list[i].high > ohlcv_list[i-1].high and ohlcv_list[i].high > ohlcv_list[i+1].high:
            local_highs.append(ohlcv_list[i].high)
        if ohlcv_list[i].low < ohlcv_list[i-1].low and ohlcv_list[i].low < ohlcv_list[i+1].low:
            local_lows.append(ohlcv_list[i].low)

    if ohlcv_list[0].high >= max(c.high for c in ohlcv_list[1:5]):
        local_highs.insert(0, ohlcv_list[0].high)
    if ohlcv_list[-1].high >= max(c.high for c in ohlcv_list[-5:]):
        local_highs.append(ohlcv_list[-1].high)
    if ohlcv_list[0].low <= min(c.low for c in ohlcv_list[1:5]):
        local_lows.insert(0, ohlcv_list[0].low)
    if ohlcv_list[-1].low <= min(c.low for c in ohlcv_list[-5:]):
        local_lows.append(ohlcv_list[-1].low)

    resistance_levels = _cluster_levels(local_highs, tolerance)
    support_levels = _cluster_levels(local_lows, tolerance)

    current_price = ohlcv_list[-1].close

    nearest_resistance = None
    for r in sorted(resistance_levels):
        if r > current_price:
            nearest_resistance = r
            break

    nearest_support = None
    for s in sorted(support_levels, reverse=True):
        if s < current_price:
            nearest_support = s
            break

    return SupportResistance(
        support_levels=[round(s, 2) for s in sorted(support_levels)],
        resistance_levels=[round(r, 2) for r in sorted(resistance_levels)],
        nearest_support=round(nearest_support, 2) if nearest_support else None,
        nearest_resistance=round(nearest_resistance, 2) if nearest_resistance else None
    )


def _cluster_levels(levels: list, tolerance: float) -> list:
    if not levels:
        return []

    sorted_levels = sorted(levels)
    clusters = [[sorted_levels[0]]]

    for level in sorted_levels[1:]:
        if level <= clusters[-1][-1] * (1 + tolerance):
            clusters[-1].append(level)
        else:
            clusters.append([level])

    return [sum(cluster) / len(cluster) for cluster in clusters]


def calc_volume_ratio(candles: list, period: int = 5) -> float:
    if not candles or len(candles) < period + 1:
        return 1.0

    ohlcv_list = [OHLCV.from_dict(c) if isinstance(c, dict) else c for c in candles]

    recent_volumes = [c.volume for c in ohlcv_list[-period:]]
    avg_volume = sum(recent_volumes) / period

    current_volume = ohlcv_list[-1].volume

    return round(current_volume / avg_volume, 2) if avg_volume > 0 else 1.0


def calc_momentum(candles: list, period: int = 10) -> float:
    if not candles or len(candles) < period + 1:
        return 0.0

    ohlcv_list = [OHLCV.from_dict(c) if isinstance(c, dict) else c for c in candles]

    current_close = ohlcv_list[-1].close
    past_close = ohlcv_list[-period].close

    return round(((current_close - past_close) / past_close) * 100, 2) if past_close != 0 else 0.0


def calc_rsi(candles: list, period: int = 14) -> float:
    if not candles or len(candles) < period + 1:
        return 50.0

    ohlcv_list = [OHLCV.from_dict(c) if isinstance(c, dict) else c for c in candles]

    gains = []
    losses = []

    for i in range(1, len(ohlcv_list)):
        change = ohlcv_list[i].close - ohlcv_list[i-1].close
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    if len(gains) < period:
        return 50.0

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return round(rsi, 2)


def calc_full_indicators(candles: list) -> dict:
    ohlcv_list = [OHLCV.from_dict(c) if isinstance(c, dict) else c for c in candles]

    if not ohlcv_list:
        return {}

    current_price = ohlcv_list[-1].close

    atr_result = calc_atr(candles)
    vwap_result = calc_vwap(candles)
    sr_levels = calc_support_resistance_levels(candles)
    volume_ratio = calc_volume_ratio(candles)
    momentum = calc_momentum(candles)
    rsi = calc_rsi(candles)
    stop_loss_info = calc_atr_stop_loss(current_price, atr_result.atr)

    return {
        "price": current_price,
        "date": ohlcv_list[-1].date,
        "atr": atr_result,
        "vwap": vwap_result,
        "support_resistance": sr_levels,
        "volume_ratio": volume_ratio,
        "momentum": momentum,
        "rsi": rsi,
        "stop_loss": stop_loss_info,
        "interpretation": _interpret_indicators(current_price, vwap_result.vwap, rsi, volume_ratio, momentum)
    }


def _interpret_indicators(price: float, vwap: float, rsi: float, vol_ratio: float, momentum: float) -> str:
    signals = []

    if vwap > 0:
        if price > vwap:
            signals.append("价格位于VWAP上方，偏多")
        elif price < vwap:
            signals.append("价格位于VWAP下方，偏空")

    if rsi > 70:
        signals.append("RSI超买，可能回调")
    elif rsi < 30:
        signals.append("RSI超卖，可能反弹")

    if vol_ratio > 1.5:
        signals.append("成交量异常放大，关注异动")
    elif vol_ratio < 0.5:
        signals.append("成交量萎缩，市场参与度低")

    if momentum > 5:
        signals.append("动量强劲，上涨趋势")
    elif momentum < -5:
        signals.append("动量疲弱，下跌趋势")

    return "; ".join(signals) if signals else "指标信号中性"


if __name__ == "__main__":
    sample_candles = [
        {"date": "2026-04-01", "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.3, "volume": 1000000},
        {"date": "2026-04-02", "open": 10.3, "high": 10.8, "low": 10.2, "close": 10.6, "volume": 1200000},
        {"date": "2026-04-03", "open": 10.6, "high": 11.0, "low": 10.4, "close": 10.8, "volume": 1500000},
        {"date": "2026-04-07", "open": 10.8, "high": 11.2, "low": 10.7, "close": 11.0, "volume": 1800000},
        {"date": "2026-04-08", "open": 11.0, "high": 11.5, "low": 10.9, "close": 11.3, "volume": 2000000},
    ]

    indicators = calc_full_indicators(sample_candles)

    print("=== 技术指标计算结果 ===")
    print(f"当前价格: {indicators['price']}")
    print(f"日期: {indicators['date']}")
    print(f"ATR(14): {indicators['atr'].atr}")
    print(f"VWAP: {indicators['vwap'].vwap}")
    print(f"VWAP偏离: {indicators['vwap'].deviation_pct}%")
    print(f"RSI: {indicators['rsi']}")
    print(f"量比: {indicators['volume_ratio']}")
    print(f"动量: {indicators['momentum']}%")
    print(f"止损价: {indicators['stop_loss']['stop_loss']}")
    print(f"最近支撑: {indicators['support_resistance'].nearest_support}")
    print(f"最近压力: {indicators['support_resistance'].nearest_resistance}")
    print(f"信号解读: {indicators['interpretation']}")
