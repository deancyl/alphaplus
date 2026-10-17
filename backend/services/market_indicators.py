"""Live market indicators — every number computed at request time.

These four indicator families used to be read out of SQLite tables
(``market_fear_greed_sentiment_history``, ``bond_equity_yield_spread_history``,
``market_style_strength_history``, ``market_crowding_valuation_history``,
``index_valuation_history``).  An audit of those tables showed they were never
written by this codebase — a one-off external load, frozen at 2026-05-25, and
containing placeholder constants rather than market data:

    pe_ttm .................... 15.0 across every ERP row
    treasury_yield_10y ........ 2.5 across every ERP row
    pe_ttm (valuation) ........ exactly 3 distinct values over 2000 rows
    factor_margin_ratio ....... 50.0 across every fear/greed row

So this module replaces the reads with real computation over live feeds.  The
rule it follows is research-terminal's:

    a figure is either computed from a named live source with a stated caliber,
    or it is declared unavailable.  It is never a placeholder.

Every function returns ``(rows, meta)``.  ``meta`` carries ``asOf`` (the date
the market printed), ``sources`` (which feed served which part), ``caliber``
(the formula, so the number can be re-derived) and ``limits`` (what the
caliber deliberately leaves out).
"""
from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from typing import Any, Iterable, Sequence

import httpx

from backend.services.quote_sources import (
    INDEX_UNIVERSE,
    UpstreamError,
    fetch_breadth,
    fetch_daily_bars,
    fetch_futures_daily,
    fetch_index_bars,
    fetch_index_pe,
    fetch_index_quotes,
    fetch_margin_series,
    fetch_sw_industries,
    fetch_treasury_daily,
    fetch_treasury_yields,
    latest_trade_date,
    num,
    rnd,
)

logger = logging.getLogger(__name__)

TRAILING_DAYS = 260  #: one trading year — the window every percentile uses.
FEAR_GREED_ROWS = 30
ERP_ROWS = 120
STYLE_ROWS = 120
VALUATION_ROWS = 260

# Fear/greed bands. Same breakpoints CNN uses, so the words mean what a reader
# already expects them to mean.
SENTIMENT_BANDS = (
    (25, "极度恐惧"),
    (45, "恐惧"),
    (56, "中性"),
    (76, "贪婪"),
    (101, "极度贪婪"),
)


def sentiment_label(score: float | None) -> str:
    if score is None:
        return "未知"
    for ceiling, label in SENTIMENT_BANDS:
        if score < ceiling:
            return label
    return "极度贪婪"


def _pct_rank(history: Sequence[float], value: float) -> float | None:
    """Where ``value`` sits in ``history``, as 0-100.

    Returns ``None`` rather than 0 when there is nothing to rank against — a
    missing sample and a bottom-of-range sample are different facts.
    """
    clean = [x for x in history if x is not None and x == x]
    if not clean:
        return None
    below = sum(1 for x in clean if x < value)
    equal = sum(1 for x in clean if x == value)
    return round(100.0 * (below + 0.5 * equal) / len(clean), 2)


def _daily_returns(closes: Sequence[float]) -> list[float]:
    out: list[float] = []
    for previous, current in zip(closes, closes[1:]):
        if previous and previous == previous:
            out.append(current / previous - 1.0)
    return out


def _realised_vol(returns: Sequence[float], window: int = 20) -> list[float]:
    """Annualised realised volatility over ``window`` days (252 sessions)."""
    out: list[float] = []
    for i in range(window - 1, len(returns)):
        chunk = returns[i - window + 1: i + 1]
        mean = sum(chunk) / len(chunk)
        variance = sum((r - mean) ** 2 for r in chunk) / len(chunk)  # ddof=0
        out.append(math.sqrt(variance) * math.sqrt(252) * 100)
    return out


def _shift(values: Sequence[Any], periods: int) -> list[Any]:
    return list(values[:-periods]) if periods and periods < len(values) else []


def _meta(
    as_of: str,
    source: str,
    caliber: str,
    sources: dict[str, dict] | None = None,
    limits: Iterable[str] = (),
) -> dict:
    return {
        "asOf": as_of,
        "source": source,
        "caliber": caliber,
        "sources": sources or {},
        "limits": [str(item) for item in limits],
    }


# --- 1. fear & greed ---------------------------------------------------------

FEAR_GREED_CALIBER = (
    "六因子 0-100 等权平均（composite = 六因子算术平均），50 为中性。"
    "每个因子先算原始值，再取其在近一年(trailing 250 交易日)样本中的百分位，"
    "高分统一代表「更贪婪」：\n"
    "1) factor_volatility    = 100 - pct_rank(沪深300 20日年化波动率)  → 波动越低越贪婪\n"
    "2) factor_safe_haven    = pct_rank(z(沪深300 近20日收益) - z(国债期货T0 近20日收益)) "
    "→ 两条腿各自按近一年标准化后取差，债强于股越恐惧\n"
    "3) factor_margin_ratio  = pct_rank(上交所两融余额 20日环比) → 杠杆资金加仓越贪婪\n"
    "4) factor_volume_deviation = pct_rank(沪深300 近20日上涨日成交量占比) → 放量上行越贪婪\n"
    "5) factor_futures_basis = pct_rank(IF0主力/沪深300 收盘价比值) → 期货升水越贪婪\n"
    "6) factor_stock_strength = pct_rank(沪深300 近20日收益) → 成分股走强越贪婪\n"
    "本口径为 live_v2：原库表因子为占位常数（margin/futures_basis/stock_strength 恒为 50.0），"
    "无法反推原式，故在此明示新口径。"
)


async def compute_fear_greed(client: httpx.AsyncClient) -> tuple[list[dict], dict]:
    """Six-factor market sentiment, computed from live bars and live leverage."""
    sources: dict[str, dict] = {}
    limits: list[str] = []

    hs300 = await fetch_index_bars(client, "000300", days=TRAILING_DAYS + 40)
    csi500 = await fetch_index_bars(client, "000905", days=TRAILING_DAYS + 40)
    sources["沪深300日线"] = {"status": "ok", "provider": hs300.source, "asOf": hs300.as_of}
    sources["中证500日线"] = {"status": "ok", "provider": csi500.source, "asOf": csi500.as_of}

    hs_close = [bar.close for bar in hs300.bars]
    hs_ret = _daily_returns(hs_close)
    bar_dates = [bar.date for bar in hs300.bars]  # aligned 1:1 with hs_close
    hs_dates = bar_dates[1:]  # date of the bar each element of hs_ret lands on
    csi_ret = _daily_returns([bar.close for bar in csi500.bars])
    csi_by_date = dict(zip([b.date for b in csi500.bars][1:], csi_ret))

    vols = _realised_vol(hs_ret, 20)
    # hs_ret[k] is the return into hs_close[k+1], so a 20-day window ending at
    # bar i belongs to bar_dates[i] — not to hs_dates[i-1].
    vol_dates = bar_dates[20: 20 + len(vols)]

    # up-day volume share, the advance/decline-volume idea expressed on one index
    up_volume_ratio: list[float] = []
    up_ratio_dates: list[str] = []
    for i in range(19, len(hs300.bars)):
        chunk = hs300.bars[i - 19: i + 1]
        total = sum(b.volume for b in chunk if b.volume)
        if total <= 0:
            continue
        up = sum(
            b.volume
            for b, prev in zip(chunk[1:], chunk[:-1])
            if b.close > prev.close and b.volume
        )
        up_volume_ratio.append(100.0 * up / total)
        up_ratio_dates.append(chunk[-1].date)

    # futures basis: IF0 main vs the spot index, level not return
    basis_ratio: list[float] = []
    basis_dates: list[str] = []
    try:
        fut = await fetch_futures_daily("IF0")
        sources["股指期货IF0"] = {"status": "ok", "provider": fut.source, "asOf": fut.as_of}
        spot_by_date = dict(zip(hs_dates, hs_close[1:]))
        for point in fut.points:
            spot = spot_by_date.get(point["date"])
            if spot and point["close"]:
                basis_ratio.append(point["close"] / spot)
                basis_dates.append(point["date"])
    except UpstreamError as exc:
        sources["股指期货IF0"] = {"status": "error", "error": exc.code}
        limits.append(f"期货基差因子不可用（{exc.code}），综合分按其余因子平均。")

    # leverage: 20-day change of the SSE two-margin balance
    margin_growth: list[float] = []
    margin_dates: list[str] = []
    try:
        today = date.today()
        margin = await fetch_margin_series(
            (today - timedelta(days=TRAILING_DAYS * 2)).strftime("%Y%m%d"),
            today.strftime("%Y%m%d"),
        )
        sources["上交所两融"] = {"status": "ok", "provider": margin.source, "asOf": margin.as_of}
        balances = [p["balance"] for p in margin.points]
        dates = [p["date"] for p in margin.points]
        for i in range(20, len(balances)):
            previous = balances[i - 20]
            if previous:
                margin_growth.append(100.0 * (balances[i] / previous - 1.0))
                margin_dates.append(dates[i])
    except UpstreamError as exc:
        sources["上交所两融"] = {"status": "error", "error": exc.code}
        limits.append(f"融资余额因子不可用（{exc.code}），综合分按其余因子平均。")

    # safe haven: stock minus bond over 20 sessions
    safe_haven: list[float] = []
    safe_dates: list[str] = []
    try:
        fut_bond = await fetch_futures_daily("T0")
        sources["国债期货T0"] = {"status": "ok", "provider": fut_bond.source, "asOf": fut_bond.as_of}
        bond_close = [p["close"] for p in fut_bond.points]
        bond_day = [p["date"] for p in fut_bond.points]
        # 20-session bond return keyed by the session it ends on. Doing this by
        # value lookup instead of by index matters: the same close prints many
        # times, so a value search lands on the wrong window.
        bond20_by_date: dict[str, float] = {
            bond_day[i]: bond_close[i] / bond_close[i - 20] - 1.0
            for i in range(20, len(bond_close))
            if bond_close[i - 20]
        }
        stock20_by_date: dict[str, float] = {
            bar_dates[i]: hs_close[i] / hs_close[i - 20] - 1.0
            for i in range(20, len(hs_close))
            if hs_close[i - 20]
        }
        # Rank the *surprise*, not the raw difference. Bond returns are roughly
        # 1/50th the scale of equity returns, so an unscaled
        # pct_rank(stock20 - bond20) collapses to pct_rank(stock20) and the
        # factor silently becomes a second copy of stock strength. Z-scoring
        # each leg against its own trailing year makes a genuinely bond-led
        # flight to quality read as fear.
        common = [d for d in sorted(set(stock20_by_date) & set(bond20_by_date))]
        stock_raw = [stock20_by_date[d] for d in common]
        bond_raw = [bond20_by_date[d] for d in common]
        stock_z = _zscore_series(stock_raw)
        bond_z = _zscore_series(bond_raw)
        spread = [s - b for s, b in zip(stock_z, bond_z)]
        safe_haven.extend(spread)
        safe_dates.extend(common)
    except UpstreamError as exc:
        sources["国债期货T0"] = {"status": "error", "error": exc.code}
        limits.append(f"避险情绪因子不可用（{exc.code}），综合分按其余因子平均。")

    # Align every factor onto its own dates so nothing is mixed across sessions.
    factor_tables = {
        "factor_volatility": _series_with_pct(vol_dates, vols, invert=True),
        "factor_safe_haven": _series_with_pct(safe_dates, safe_haven),
        "factor_margin_ratio": _series_with_pct(margin_dates, margin_growth),
        "factor_volume_deviation": _series_with_pct(up_ratio_dates, up_volume_ratio),
        "factor_futures_basis": _series_with_pct(basis_dates, basis_ratio),
        "factor_stock_strength": _series_with_pct(
            bar_dates[20:],
            [hs_close[i] / hs_close[i - 20] - 1.0 for i in range(20, len(hs_close))],
        ),
    }

    all_dates = sorted({d for table in factor_tables.values() for d in table})
    rows: list[dict] = []
    for day in all_dates[-FEAR_GREED_ROWS:]:
        factors: dict[str, float | None] = {
            key: table.get(day) for key, table in factor_tables.items()
        }
        present = [v for v in factors.values() if v is not None]
        composite = rnd(sum(present) / len(present), 2) if present else None
        row = {"trade_date": day, "composite_score": composite}
        row.update({k: (rnd(v, 2) if v is not None else None) for k, v in factors.items()})
        row["sentiment_status"] = sentiment_label(composite)
        row["factors_reported"] = len(present)
        rows.append(row)

    rows.reverse()  # newest first, matching the previous contract
    as_of = rows[0]["trade_date"] if rows else latest_trade_date()
    return rows, _meta(as_of, "live", FEAR_GREED_CALIBER, sources, limits)


def _zscore_series(values: Sequence[float], window: int = TRAILING_DAYS) -> list[float]:
    """Rolling z-score against each point's own trailing window.

    Sample standard deviation, and ``0.0`` (not the raw value, not a gap) when
    the window is flat — a flat window carries no information about surprise.
    """
    out: list[float] = []
    for index in range(len(values)):
        chunk = values[max(0, index - window + 1): index + 1]
        if len(chunk) < 5:
            out.append(0.0)
            continue
        mean = sum(chunk) / len(chunk)
        variance = sum((v - mean) ** 2 for v in chunk) / (len(chunk) - 1)
        sd = math.sqrt(variance)
        out.append((values[index] - mean) / sd if sd > 0 else 0.0)
    return out


def _series_with_pct(
    dates: Sequence[str], raw: Sequence[float], invert: bool = False
) -> dict[str, float]:
    """Percentile-rank a dated series against its own trailing window."""
    out: dict[str, float] = {}
    for index, (day, value) in enumerate(zip(dates, raw)):
        if value is None or value != value:
            continue
        window = raw[max(0, index - TRAILING_DAYS): index + 1]
        score = _pct_rank(window, value)
        if score is None:
            continue
        out[day] = 100.0 - score if invert else score
    return out


# --- 2. equity risk premium --------------------------------------------------

ERP_CALIBER = (
    "erp_spread = 100/pe_ttm - treasury_yield_10y(%)，即股票盈利收益率相对10年期国债的利差(百分点)。"
    "pe_ttm 取乐咕乐股滚动市盈率，treasury_yield_10y 取中债国债收益率曲线10年期。"
    "percentile_rank_10y 为该利差在近一年样本中的百分位，越高代表股票相对债券越便宜。"
    "moving_mean_10y / std_dev_1y / std_dev_2y 为利差的滚动均值与标准差通道。"
)

RISK_FREE_TYPES = ("treasury_10y", "cdb_10y", "dr007", "deposit_1y", "deposit_3y", "deposit_5y")


async def compute_erp(
    client: httpx.AsyncClient, index_code: str = "000300", risk_free_type: str = "treasury_10y"
) -> tuple[list[dict], dict]:
    """Live ERP: real TTM PE against a real 10-year government yield."""
    if index_code not in INDEX_UNIVERSE:
        raise UpstreamError("invalid_index_code")
    if risk_free_type not in RISK_FREE_TYPES:
        raise UpstreamError("invalid_risk_free_type")

    sources: dict[str, dict] = {}
    limits: list[str] = []

    pe = await fetch_index_pe(index_code)
    sources["指数市盈率"] = {"status": "ok", "provider": pe.source, "asOf": pe.as_of}

    # The valuation feed prints monthly, so the yield feed must be daily or only
    # the last couple of points would find a match and the rest would vanish.
    curve_points = await fetch_treasury_daily(
        (date.today() - timedelta(days=ERP_ROWS * 40)).strftime("%Y%m%d")
    )
    sources["国债收益率曲线"] = {
        "status": "ok",
        "provider": "www.chinamoney.com.cn",
        "asOf": curve_points[-1]["date"],
    }

    yield_by_date: dict[str, float] = {
        p["date"]: p["y10"] for p in curve_points if p.get("y10")
    }
    if not yield_by_date:
        raise UpstreamError("upstream_missing_column", "www.chinamoney.com.cn")

    # Walk the valuation history and pair each date with the nearest yield at or
    # before it — the curve prints after the close, never before.
    rows: list[dict] = []
    last_yield: float | None = None
    yield_dates = sorted(yield_by_date)
    cursor = 0
    spread_history: list[float] = []
    for point in pe.points[-ERP_ROWS:]:
        day = point["date"]
        while cursor < len(yield_dates) and yield_dates[cursor] <= day:
            last_yield = yield_by_date[yield_dates[cursor]]
            cursor += 1
        if last_yield is None or point["pe_ttm"] <= 0:
            continue
        earnings_yield = 100.0 / point["pe_ttm"]
        spread = earnings_yield - last_yield
        spread_history.append(spread)
        window = spread_history[-TRAILING_DAYS:]
        recent = window[-min(250, len(window)): -min(1, len(window) - 1)] or window
        mean = sum(recent) / len(recent)
        sd = math.sqrt(sum((s - mean) ** 2 for s in recent) / len(recent))
        rows.append(
            {
                "index_code": index_code,
                "index_name": INDEX_UNIVERSE[index_code].name,
                "trade_date": day,
                "pe_ttm": rnd(point["pe_ttm"], 4),
                "treasury_yield_10y": rnd(last_yield, 4),
                "earnings_yield": rnd(earnings_yield, 4),
                "erp_spread": rnd(spread, 4),
                "moving_mean_10y": rnd(mean, 4) if recent else None,
                "std_dev_1y_10y": rnd(sd, 4) if len(recent) > 20 else None,
                "percentile_rank_10y": _pct_rank(window, spread),
                "risk_free_rate": rnd(last_yield, 4),
                "risk_free_type": risk_free_type,
            }
        )

    if not rows:
        raise UpstreamError("no_data")

    rows.reverse()
    if risk_free_type != "treasury_10y":
        limits.append(
            f"当前 risk_free_type={risk_free_type} 的实时替代源未接入，"
            "利差仍以10年期国债计算，risk_free_type 字段仅记录请求值。"
        )
    meta = _meta(
        rows[0]["trade_date"], "live", ERP_CALIBER, sources, limits
    )
    meta["index_name"] = INDEX_UNIVERSE[index_code].name
    return rows[:ERP_ROWS], meta


# --- 3. style strength -------------------------------------------------------

STYLE_CALIBER = (
    "ratio_value = 沪深300 收盘价 / 中证500 收盘价 × 100，即大盘相对小盘的价格比。"
    "percentile_rank_3y 为该比值在近三年(750 交易日)样本中的百分位，"
    "越高代表大盘风格越占优。两端日线均由腾讯/新浪实时抓取。"
)


async def compute_style_strength(client: httpx.AsyncClient) -> tuple[list[dict], dict]:
    """Large vs small cap relative strength from live daily bars."""
    big = await fetch_daily_bars(client, "sh000300", "sh000300", TRAILING_DAYS * 3 + 60, True)
    small = await fetch_daily_bars(client, "sh000905", "sh000905", TRAILING_DAYS * 3 + 60, True)
    if not big.bars or not small.bars:
        raise UpstreamError("no_bars")

    small_close = dict((bar.date, bar.close) for bar in small.bars)
    ratios: list[tuple[str, float]] = [
        (bar.date, 100.0 * bar.close / small_close[bar.date])
        for bar in big.bars
        if bar.date in small_close and small_close[bar.date]
    ]
    if not ratios:
        raise UpstreamError("no_bars")

    values = [r for _, r in ratios]
    rows = []
    for (day, ratio) in ratios[-STYLE_ROWS:]:
        window = values[-TRAILING_DAYS * 3:]
        rows.append(
            {
                "trade_date": day,
                "index_code_num": "000300",
                "index_code_den": "000905",
                "ratio_value": rnd(ratio, 4),
                "percentile_rank_3y": _pct_rank(window, ratio),
            }
        )
    rows.reverse()
    sources = {
        "沪深300日线": {"status": "ok", "provider": big.source, "asOf": big.as_of},
        "中证500日线": {"status": "ok", "provider": small.source, "asOf": small.as_of},
    }
    return rows, _meta(rows[0]["trade_date"], "live", STYLE_CALIBER, sources)


# --- 4. index valuation ------------------------------------------------------

VALUATION_CALIBER = (
    "pe_ttm 取乐咕乐股滚动市盈率；percentile_rank_10y 为该 PE 在近三年(750 交易日)"
    "样本中的百分位——注意 PE 越低分位越低代表越便宜，此处保留上游口径不翻转。"
    "moving_mean_10y 为 PE 的滚动均值。index_close_price 为同一来源的收盘点位。"
    "该指数若无实时估值源，则整体声明 unavailable 而非回退到库表常数。"
)


async def compute_index_valuation_history(
    client: httpx.AsyncClient, index_code: str, days: int = VALUATION_ROWS
) -> tuple[list[dict], dict]:
    """Live PE(TTM) history with percentile — replaces the frozen 3-value table."""
    pe = await fetch_index_pe(index_code)
    values = [p["pe_ttm"] for p in pe.points]
    rows = []
    for point in pe.points[-days:]:
        index = pe.points.index(point)
        window = values[max(0, index - TRAILING_DAYS * 3): index + 1]
        mean = sum(window) / len(window)
        rows.append(
            {
                "index_code": index_code,
                "trade_date": point["date"],
                "pe_ttm": rnd(point["pe_ttm"], 4),
                "percentile_rank_10y": _pct_rank(window, point["pe_ttm"]),
                "moving_mean_10y": rnd(mean, 4),
            }
        )
    rows.reverse()
    sources = {"指数市盈率": {"status": "ok", "provider": pe.source, "asOf": pe.as_of}}
    return rows, _meta(pe.as_of, "live", VALUATION_CALIBER, sources)


# --- 5. crowding -------------------------------------------------------------

CROWDING_CALIBER = (
    "按申万一级行业实时估值计算：pe_percentile = 该行业 TTM 市盈率在全部一级行业中的百分位；"
    "crowding_score = 100 × 归一化(pe_percentile × 0.7 + 市净率分位 × 0.3)，"
    "即「贵且被抢」的程度，0 为无人问津、100 为极度拥挤。"
    "close_price 由申万一级指数日线实时抓取，无日线时为 null（不编造点位）。"
)


async def compute_crowding(
    client: httpx.AsyncClient, category: str = "sector", top: int = 8
) -> tuple[list[dict], dict]:
    """Sector crowding from the live Shenwan level-1 valuation snapshot."""
    if category != "sector":
        raise UpstreamError("invalid_category")

    industries = await fetch_sw_industries()
    rows_in = [p for p in industries.points if p.get("pe_ttm") is not None and p["pe_ttm"] > 0]
    if not rows_in:
        raise UpstreamError("no_data")

    pes = sorted(p["pe_ttm"] for p in rows_in)
    pbs = sorted(p["pb"] for p in rows_in if p.get("pb"))

    def _rank(pool: list[float], value: float) -> float:
        below = sum(1 for x in pool if x < value)
        return 100.0 * below / max(1, len(pool) - 1) if len(pool) > 1 else 50.0

    scored = []
    for row in rows_in:
        pe_pct = _rank(pes, row["pe_ttm"])
        pb_pct = _rank(pbs, row["pb"]) if row.get("pb") and pbs else pe_pct
        scored.append(
            {
                "asset_code": row["asset_code"],
                "trade_date": latest_trade_date(),
                "category": "sector",
                "crowding_score": rnd(100.0 * (0.7 * pe_pct + 0.3 * pb_pct) / 100.0, 4),
                "pe_percentile": rnd(pe_pct, 4),
                "pb_percentile": rnd(pb_pct, 4),
                "pe_ttm": rnd(row["pe_ttm"], 4),
                "pb": rnd(row["pb"], 4) if row.get("pb") else None,
                "dividend_yield": rnd(row["dividend_yield"], 4)
                if row.get("dividend_yield")
                else None,
                "close_price": None,  # filled below only when a real index prints it
            }
        )
    scored.sort(key=lambda r: r["crowding_score"], reverse=True)

    # Attach real closes where the industry index daily feed answers.  Fetched
    # concurrently: run serially these eight calls alone cost ~13 seconds.
    closes: dict[str, tuple[float, str]] = {}
    sw_codes = {p["asset_code"]: p["sw_code"].split(".")[0] for p in industries.points}
    top_names = [r["asset_code"] for r in scored[:top]]
    try:
        import asyncio

        import akshare as ak
        from backend.services.quote_sources import run_ak

        async def one_close(name: str) -> tuple[str, tuple[float, str] | None]:
            code = sw_codes.get(name)
            if not code:
                return name, None
            try:
                frame = await run_ak(
                    lambda c=code: ak.index_hist_sw(symbol=c, period="day"), timeout=10.0
                )
            except Exception:  # noqa: BLE001 - enrichment must never fail the panel
                return name, None
            if frame is None or frame.empty or "收盘" not in frame.columns:
                return name, None
            last = frame.iloc[-1]
            return name, (float(last["收盘"]), str(last["日期"]))

        for name, value in await asyncio.gather(*(one_close(n) for n in top_names)):
            if value is not None:
                closes[name] = value
    except Exception as exc:  # noqa: BLE001 - closes are enrichment, not the metric
        logger.info("sector close enrichment unavailable: %s", type(exc).__name__)

    for row in scored[:top]:
        if row["asset_code"] in closes:
            value, day = closes[row["asset_code"]]
            row["close_price"] = rnd(value, 4)
            row["close_as_of"] = day

    sources = {
        "申万一级行业估值": {"status": "ok", "provider": industries.source, "asOf": industries.as_of},
        "申万一级指数日线": {
            "status": "ok" if closes else "skipped",
            "records": len(closes),
        },
    }
    limits = [
        "close_price 仅对可取到日线的前若干行业填充，其余为 null（不编造点位）。",
        "本口径为 live_v2：原库表 close_price 在相邻交易日之间随机跳动，非真实指数点位。",
    ]
    as_of = industries.as_of
    for day in closes.values():
        as_of = max(as_of, day[1])
    return scored, _meta(as_of, "live", CROWDING_CALIBER, sources, limits)
