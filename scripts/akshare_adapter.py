from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import logging

try:
    import akshare as ak
    import pandas as pd
    _AKSHARE_AVAILABLE = True
except ImportError:
    _AKSHARE_AVAILABLE = False

LOGGER = logging.getLogger(__name__)


@dataclass
class AKShareData:
    stock_code: str
    stock_name: str
    candles: list
    fund_flow: list
    bid_ask: dict
    news: list
    success: bool
    error_message: str = ""


class AKShareAdapter:
    def __init__(self):
        self.available = _AKSHARE_AVAILABLE
        if not self.available:
            LOGGER.warning("AKShare 未安装，请运行: pip install akshare")

    def get_realtime_quote(self, stock_code: str) -> Optional[dict]:
        if not self.available:
            return None
        try:
            df = ak.stock_bid_ask_em(symbol=stock_code)
            if df is not None:
                return df.to_dict(orient='records')[0]
        except Exception as e:
            LOGGER.error(f"获取实时报价失败: {e}")
        return None

    def get_historical_candles(
        self,
        stock_code: str,
        days: int = 60,
        adjust: str = "qfq"
    ) -> list:
        if not self.available:
            return []
        try:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
            end_date = datetime.now().strftime('%Y%m%d')

            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust
            )

            if df is not None and not df.empty:
                return [
                    {
                        "date": row['日期'],
                        "open": float(row['开盘']),
                        "high": float(row['最高']),
                        "low": float(row['最低']),
                        "close": float(row['收盘']),
                        "volume": float(row['成交量']),
                        "amount": float(row['成交额']) if '成交额' in row else 0,
                    }
                    for _, row in df.iterrows()
                ]
        except Exception as e:
            LOGGER.error(f"获取历史K线失败: {e}")
        return []

    def get_minute_data(self, stock_code: str, period: str = '1') -> list:
        if not self.available:
            return []
        try:
            symbol = f"SH{stock_code}" if stock_code.startswith('6') else f"SZ{stock_code}"
            df = ak.stock_zh_a_minute(symbol=symbol, period=period, adjust="qfq")

            if df is not None and not df.empty:
                return [
                    {
                        "datetime": row['day'],
                        "open": float(row['open']),
                        "high": float(row['high']),
                        "low": float(row['low']),
                        "close": float(row['close']),
                        "volume": float(row['volume']),
                    }
                    for _, row in df.iterrows()
                ]
        except Exception as e:
            LOGGER.error(f"获取分时数据失败: {e}")
        return []

    def get_fund_flow(self, stock_code: str, market: str = None) -> list:
        if not self.available:
            return []
        try:
            if market is None:
                market = "sh" if stock_code.startswith('6') else "sz"

            df = ak.stock_individual_fund_flow(stock=stock_code, market=market)

            if df is not None and not df.empty:
                return [
                    {
                        "date": row['日期'],
                        "close_price": float(row['收盘价']),
                        "change_pct": float(row['涨跌幅']),
                        "main_net_inflow": float(row['主力净流入-净额']),
                        "main_net_pct": float(row['主力净流入-净占比']),
                        "super_net_inflow": float(row['超大单净流入-净额']),
                        "super_net_pct": float(row['超大单净流入-净占比']),
                        "big_net_inflow": float(row['大单净流入-净额']),
                        "big_net_pct": float(row['大单净流入-净占比']),
                        "medium_net_inflow": float(row['中单净流入-净额']),
                        "small_net_inflow": float(row['小单净流入-净额']),
                    }
                    for _, row in df.iterrows()
                ]
        except Exception as e:
            LOGGER.error(f"获取资金流向失败: {e}")
        return []

    def get_news(self, stock_code: str, limit: int = 10) -> list:
        if not self.available:
            return []
        try:
            df = ak.stock_news_em(symbol=stock_code)

            if df is not None and not df.empty:
                return [
                    {
                        "publish_time": row['发布时间'],
                        "title": row['新闻标题'],
                        "url": row.get('news_url', ''),
                    }
                    for _, row in df.head(limit).iterrows()
                ]
        except Exception as e:
            LOGGER.error(f"获取新闻失败: {e}")
        return []

    def get_financial_indicators(self, stock_code: str, years: int = 2) -> list:
        if not self.available:
            return []
        try:
            start_year = datetime.now().year - years
            df = ak.stock_financial_analysis_indicator(symbol=stock_code, start_year=str(start_year))

            if df is not None and not df.empty:
                return [
                    {
                        "date": row['日期'],
                        "eps": float(row.get('摊薄每股收益(元)', 0)),
                        "roe": float(row.get('总资产利润率(%)', 0)),
                        "gross_margin": float(row.get('主营业务利润率(%)', 0)),
                        "net_margin": float(row.get('成本费用利润率(%)', 0)),
                        "operating_cf": float(row.get('每股经营性现金流(元)', 0)),
                    }
                    for _, row in df.head(8).iterrows()
                ]
        except Exception as e:
            LOGGER.error(f"获取财务指标失败: {e}")
        return []

    def get_limit_up_pool(self, trade_date: str = None) -> list:
        if not self.available:
            return []
        try:
            if trade_date is None:
                trade_date = datetime.now().strftime('%Y%m%d')

            df = ak.stock_zt_pool_em(date=trade_date)

            if df is not None and not df.empty:
                return [
                    {
                        "code": row['代码'],
                        "name": row['名称'],
                        "zt_count": row['涨停统计'],
                        "market_cap": float(row['流通市值']),
                    }
                    for _, row in df.iterrows()
                ]
        except Exception as e:
            LOGGER.error(f"获取涨停板失败: {e}")
        return []

    def get_full_data(self, stock_code: str) -> AKShareData:
        candles = self.get_historical_candles(stock_code, days=60)
        fund_flow = self.get_fund_flow(stock_code)
        bid_ask = self.get_realtime_quote(stock_code) or {}
        news = self.get_news(stock_code, limit=10)

        stock_name = ""
        if bid_ask:
            stock_name = bid_ask.get('名称', '')

        return AKShareData(
            stock_code=stock_code,
            stock_name=stock_name,
            candles=candles,
            fund_flow=fund_flow,
            bid_ask=bid_ask,
            news=news,
            success=bool(candles or fund_flow),
            error_message="" if candles else "未能获取K线数据"
        )


def format_fund_flow_summary(fund_flow: list, days: int = 5) -> dict:
    if not fund_flow:
        return {}

    recent = fund_flow[:days]
    total_main_net = sum(f['main_net_inflow'] for f in recent)
    avg_main_pct = sum(f['main_net_pct'] for f in recent) / len(recent) if recent else 0

    direction = "流入" if total_main_net > 0 else "流出"
    intensity = "强势" if abs(avg_main_pct) > 10 else "温和" if abs(avg_main_pct) > 5 else "平淡"

    return {
        "direction": direction,
        "intensity": intensity,
        "total_net": total_main_net,
        "avg_net_pct": avg_main_pct,
        "days": days,
        "summary": f"{intensity}{direction}，近{days}日主力净{'流入' if total_main_net > 0 else '流出'} {abs(total_main_net)/1e8:.2f} 亿"
    }


if __name__ == "__main__":
    print("=== AKShare 数据适配器测试 ===\n")

    adapter = AKShareAdapter()

    if not adapter.available:
        print("❌ AKShare 未安装")
        exit(1)

    stock_code = "600519"

    print(f"【1】获取 {stock_code} 完整数据...")
    data = adapter.get_full_data(stock_code)
    print(f"  股票名称: {data.stock_name}")
    print(f"  K线数据: {len(data.candles)} 条")
    print(f"  资金流向: {len(data.fund_flow)} 条")
    print(f"  新闻: {len(data.news)} 条")
    print()

    print(f"【2】K线数据（前3条）:")
    for c in data.candles[:3]:
        print(f"  {c['date']}: 收盘 {c['close']} 元")

    print(f"\n【3】资金流向摘要:")
    summary = format_fund_flow_summary(data.fund_flow)
    print(f"  {summary.get('summary', '无数据')}")

    print(f"\n【4】最新新闻:")
    for n in data.news[:3]:
        print(f"  [{n['publish_time'][:10]}] {n['title'][:50]}...")

    print(f"\n【5】涨停板（前5只）:")
    zt_pool = adapter.get_limit_up_pool()
    print(f"  今日涨停: {len(zt_pool)} 只")
    for zt in zt_pool[:5]:
        print(f"  {zt['code']} {zt['name']}")

    print("\n✅ 测试完成！")
