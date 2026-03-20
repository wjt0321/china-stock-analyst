# 报告生成相关常量，与 team_router 的 FAILURE_REASON_* 分离
# 供 generate_report 使用

SENTIMENT_MAX_IMPACT = 2.0
EMOTIONAL_NEWS_KEYWORDS = ["暴涨", "暴跌", "惊天", "炸裂", "血赚", "必涨", "必赢", "内幕", "速看"]
LOW_CREDIBILITY_HINTS = ["转载", "自媒体", "论坛", "股吧", "传闻", "小作文", "未证实"]
POSITIVE_SENTIMENT_KEYWORDS = ["利好", "增持", "中标", "回购", "增长", "上调", "突破", "创新高"]
NEGATIVE_SENTIMENT_KEYWORDS = ["利空", "减持", "处罚", "亏损", "下调", "暴雷", "跌停", "终止"]
INDUSTRY_POSITIVE_KEYWORDS = ["景气", "扩产", "提价", "复苏", "高增长", "需求回暖", "高景气"]
INDUSTRY_NEGATIVE_KEYWORDS = ["过剩", "下行", "去库存", "收缩", "需求疲弱", "价格战"]
EVENT_POSITIVE_KEYWORDS = ["中标", "回购", "增持", "政策支持", "订单", "突破"]
EVENT_NEGATIVE_KEYWORDS = ["处罚", "问询", "减持", "终止", "风险提示", "监管关注"]
EXPERT_PRICE_TOLERANCE_RATIO = 0.08
EXPECTED_EXPERT_AGENTS = {
    "industry_researcher": "expert_industry_researcher",
    "event_hunter": "expert_event_hunter",
}

FAILURE_CODE_IDENTITY_CODE_INVALID = "IDENTITY_CODE_INVALID"
FAILURE_CODE_IDENTITY_EVIDENCE_INSUFFICIENT = "IDENTITY_EVIDENCE_INSUFFICIENT"
FAILURE_CODE_IDENTITY_CODE_NAME_MISMATCH = "IDENTITY_CODE_NAME_MISMATCH"
FAILURE_CODE_IDENTITY_NAME_CODE_CONFLICT = "IDENTITY_NAME_CODE_CONFLICT"
FAILURE_CODE_PRICE_CURRENCY_UNIT_INCONSISTENT = "PRICE_CURRENCY_UNIT_INCONSISTENT"
FAILURE_CODE_PRICE_CURRENCY_UNIT_EVIDENCE_INSUFFICIENT = "PRICE_CURRENCY_UNIT_EVIDENCE_INSUFFICIENT"
FAILURE_CODE_PRICE_INVALID = "PRICE_INVALID"
FAILURE_CODE_TRADING_DAY_STALE = "TRADING_DAY_STALE"

FAILURE_REASON_TIPS = {
    "REQUEST_LIMIT_EXCEEDED": "请降低返回条数（建议<=50）后重试。",
    "TIME_RANGE_EXCEEDED": "请缩小时间范围（建议<=180天）后重试。",
    "TARGET_REQUIRED": "请补充股票代码或股票名称后再发起请求。",
    "INTENT_NOT_MATCHED": "未识别到东财意图，已降级为本地分析流程。",
    "DUPLICATE_REQUEST": "请求过于频繁，请稍后重试或补充差异化筛选条件。",
    "SYMBOL_METADATA_UNAVAILABLE": "标的元信息暂不可用，已自动降级为东财/本地流程。",
    FAILURE_CODE_IDENTITY_CODE_INVALID: "请核对股票代码格式（A股6位代码）并重新采样。",
    FAILURE_CODE_IDENTITY_EVIDENCE_INSUFFICIENT: "请补充至少两类可信来源的代码-名称证据。",
    FAILURE_CODE_IDENTITY_CODE_NAME_MISMATCH: "请统一代码与名称映射，移除冲突来源后重试。",
    FAILURE_CODE_IDENTITY_NAME_CODE_CONFLICT: "请确认同名主体对应唯一代码并重新抓取。",
    FAILURE_CODE_PRICE_CURRENCY_UNIT_INCONSISTENT: "请统一价格币种与单位为人民币元/股。",
    FAILURE_CODE_PRICE_CURRENCY_UNIT_EVIDENCE_INSUFFICIENT: "请补充至少两类来源的币种单位证据。",
    FAILURE_CODE_PRICE_INVALID: "请校验价格是否处于 0.1~600.0 元区间。",
    FAILURE_CODE_TRADING_DAY_STALE: "请重采请求交易日内的分钟级行情时间戳。",
}

PRICE_VALID_MIN = 0.1
PRICE_VALID_MAX = 600.0
