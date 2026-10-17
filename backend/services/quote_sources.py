"""Live upstream access layer.

Modeled on research-terminal's ``functions/sources.ts``: the browser never
supplies a URL, every destination is a fixed host on the allowlist, and every
figure is fetched at request time with a declared source.

Four rules this module exists to enforce:

1. **Host allowlist, https only, redirect must land on the same host.** A quote
   endpoint can never turn the backend into an open proxy.
2. **Every datum has a primary *and* a backup upstream**, and the response says
   which one actually served it (``source``).  The East Money push2 cluster is
   reachable from this box today but has been dead before — so it is never the
   only path.
3. **Failures are declared, not disguised.**  A failed upstream raises
   ``UpstreamError`` with a whitelisted-style code; callers turn that into an
   ``unavailable`` source entry instead of substituting a number.
4. **Business dates travel with the data.**  ``asOf`` is the date the *market*
   printed, not the moment we happened to answer.
"""
from __future__ import annotations

import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Sequence

import httpx

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 8.0

# --- host allowlist ----------------------------------------------------------

# Only these hosts may be contacted, and only on their own host after redirects.
# Verified reachable from this box (see docs/RESEARCH_REALTIME_DATA.md §2.1).
ALLOWED_HOSTS: frozenset[str] = frozenset(
    {
        "push2.eastmoney.com",
        "push2delay.eastmoney.com",
        "82.push2.eastmoney.com",
        "17.push2.eastmoney.com",
        "40.push2.eastmoney.com",
        "88.push2.eastmoney.com",
        "push2ex.eastmoney.com",
        "qt.gtimg.cn",
        "web.ifzq.gtimg.cn",
        "vip.stock.finance.sina.com.cn",
        "hq.sinajs.cn",
        "fund.eastmoney.com",
        "api.fund.eastmoney.com",
        "www.chinamoney.com.cn",
        "api.frankfurter.dev",
        "legulegu.com",
    }
)

UPSTREAM_LABELS: dict[str, str] = {
    "push2.eastmoney.com": "东方财富 实时行情",
    "82.push2.eastmoney.com": "东方财富 实时行情(镜像82)",
    "17.push2.eastmoney.com": "东方财富 实时行情(镜像17)",
    "40.push2.eastmoney.com": "东方财富 实时行情(镜像40)",
    "88.push2.eastmoney.com": "东方财富 实时行情(镜像88)",
    "push2delay.eastmoney.com": "东方财富 实时行情(延迟)",
    "push2ex.eastmoney.com": "东方财富 涨跌家数/涨跌停池",
    "qt.gtimg.cn": "腾讯财经 实时快照",
    "web.ifzq.gtimg.cn": "腾讯财经 日K线",
    "vip.stock.finance.sina.com.cn": "新浪财经 日K线/涨幅榜",
    "hq.sinajs.cn": "新浪财经 实时快照",
    "fund.eastmoney.com": "东方财富 基金排行",
    "api.fund.eastmoney.com": "东方财富 基金净值",
    "www.chinamoney.com.cn": "中国外汇交易中心 利率/中间价",
    "api.frankfurter.dev": "ECB 参考汇率",
    "legulegu.com": "乐咕乐股 指数估值",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class UpstreamError(RuntimeError):
    """An upstream call failed. ``code`` is safe to expose to a client."""

    def __init__(self, code: str, host: str | None = None):
        super().__init__(code)
        self.code = code
        self.host = host


def _safe_cause(exc: BaseException) -> str:
    """Reduce an exception to a code with no URL, message or stack in it."""
    name = type(exc).__name__
    raw = str(exc)
    code = re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_")[:60] or name
    return f"upstream_{name}_{code}".lower()[:90]


def _host_of(url: str) -> str:
    return httpx.URL(url).host


# --- fetch primitives --------------------------------------------------------

def _check_url(url: str) -> None:
    target = httpx.URL(url)
    if target.scheme != "https":
        raise UpstreamError("upstream_not_allowed")
    if target.host not in ALLOWED_HOSTS:
        raise UpstreamError("upstream_not_allowed")


async def fetch_text(
    client: httpx.AsyncClient,
    url: str,
    referer: str | None = None,
    encoding: str = "utf-8",
) -> str:
    """Fetch a whitelisted https URL and decode it.

    Same-host redirects are followed; a hop to another host is rejected so a
    trusted endpoint can never turn this backend into an open proxy.
    """
    _check_url(url)
    host = _host_of(url)
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}
    if referer:
        headers["Referer"] = referer
    try:
        response = await client.get(url, headers=headers, follow_redirects=True, timeout=TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        raise UpstreamError(_safe_cause(exc), host) from exc

    # A redirect off the original host means the target moved somewhere we
    # never allowed.
    if response.url.host != host:
        raise UpstreamError("upstream_redirect", host)
    if response.status_code >= 400:
        raise UpstreamError(f"upstream_{response.status_code}", host)

    if encoding.lower() in ("utf-8", "utf8"):
        return response.text
    try:
        return response.content.decode(encoding)
    except (LookupError, UnicodeDecodeError):
        # Runtime without a GBK label still yields correct numbers; only the
        # embedded Chinese names degrade. That beats failing the whole panel.
        return response.content.decode("utf-8", "replace")


async def fetch_json(
    client: httpx.AsyncClient,
    url: str,
    referer: str | None = None,
    encoding: str = "utf-8",
) -> Any:
    import json as _json

    text = await fetch_text(client, url, referer, encoding)
    try:
        return _json.loads(text)
    except ValueError as exc:
        raise UpstreamError("upstream_bad_json", _host_of(url)) from exc


# --- reference constants -----------------------------------------------------

@dataclass(frozen=True)
class IndexRef:
    """One index in the universe: its code plus how each upstream names it."""

    code: str
    name: str
    secid: str  # eastmoney ulist
    tx: str  # tencent qt.gtimg / fqkline
    sina: str  # sina kline
    lg: str | None = None  # legulegu PE symbol, None when it publishes none


INDEX_UNIVERSE: dict[str, IndexRef] = {
    ref.code: ref
    for ref in (
        IndexRef("000001", "上证指数", "1.000001", "sh000001", "sh000001", "上证综指"),
        IndexRef("000300", "沪深300", "1.000300", "sh000300", "sh000300", "沪深300"),
        IndexRef("000905", "中证500", "1.000905", "sh000905", "sh000905", "中证500"),
        IndexRef("000852", "中证1000", "1.000852", "sh000852", "sh000852", "中证1000"),
        IndexRef("000016", "上证50", "1.000016", "sh000016", "sh000016", "上证50"),
        IndexRef("000903", "中证100", "1.000903", "sh000903", "sh000903", "中证100"),
        IndexRef("000906", "中证800", "1.000906", "sh000906", "sh000906", "中证800"),
        IndexRef("399001", "深证成指", "0.399001", "sz399001", "sz399001"),
        IndexRef("399006", "创业板指", "0.399006", "sz399006", "sz399006"),
        IndexRef("399330", "深证100", "0.399330", "sz399330", "sz399330", "深证100"),
        IndexRef("899050", "北证50", "0.899050", "bj899050", "bj899050"),
    )
}

#: Display order — object keys would sort numeric-looking codes, this must not.
INDEX_CODES: list[str] = ["000001", "000300", "000905", "000852", "399006", "000016", "899050"]

# Numbered eastmoney mirrors, rotated the way akshare rotates them: the primary
# host rejects or drops a caller, so the cursor walks the list.
PUSH2_HOSTS: list[str] = [
    "push2.eastmoney.com",
    "82.push2.eastmoney.com",
    "17.push2.eastmoney.com",
    "40.push2.eastmoney.com",
    "88.push2.eastmoney.com",
    "push2delay.eastmoney.com",
]

_quotes_cursor = 0
#: Host that served the most recent batch quote, surfaced by /api/health.
last_quote_host: str = "none"


def is_valid_index_code(code: str) -> bool:
    return code in INDEX_UNIVERSE


# --- blocking akshare calls, kept off the event loop -------------------------

_AK_EXECUTOR = ThreadPoolExecutor(max_workers=6, thread_name_prefix="live_src")


async def run_ak(call: Callable[[], Any], timeout: float = 12.0) -> Any:
    """Run a blocking akshare call on a dedicated pool with a deadline.

    akshare's synchronous HTTP is why several endpoints took 20-36s while
    holding the event loop; a pool plus a hard timeout keeps one slow upstream
    from stalling every other request.
    """
    loop = asyncio.get_running_loop()
    task = loop.run_in_executor(_AK_EXECUTOR, call)
    return await asyncio.wait_for(task, timeout=timeout)


# --- small numeric helpers ---------------------------------------------------

def num(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return 0.0
    return out if out == out and out not in (float("inf"), float("-inf")) else 0.0


def rnd(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


# --- market breadth ----------------------------------------------------------

@dataclass
class Breadth:
    advance: int
    decline: int
    unchanged: int
    total: int
    as_of: str
    source: str = "push2ex.eastmoney.com"

    @property
    def date(self) -> str:
        return self.as_of


async def fetch_breadth(client: httpx.AsyncClient) -> Breadth:
    """Whole-market advance/decline from East Money's distribution histogram.

    research-terminal uses this instead of the push2 ``f104/f105/f106`` fields
    precisely because the push2 quote hosts are the ones that go missing.
    """
    url = (
        "https://push2ex.eastmoney.com/getTopicZDFenBu"
        "?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt"
    )
    payload = await fetch_json(client, url, "https://quote.eastmoney.com/ztb/detail")
    buckets: list = (payload.get("data") or {}).get("fenbu") or []
    if not buckets:
        raise UpstreamError("upstream_empty_fenbu", "push2ex.eastmoney.com")
    advance = decline = unchanged = 0
    for bucket in buckets:
        for key, value in bucket.items():
            count = int(num(value))
            pct = num(key)
            if pct > 0:
                advance += count
            elif pct < 0:
                decline += count
            else:
                unchanged += count
    as_of = str((payload.get("data") or {}).get("qdate") or "")
    if len(as_of) == 8:
        as_of = f"{as_of[:4]}-{as_of[4:6]}-{as_of[6:]}"
    return Breadth(advance, decline, unchanged, advance + decline + unchanged, as_of)


# --- realtime quotes ---------------------------------------------------------

@dataclass
class Quote:
    code: str
    name: str
    price: float
    change: float
    change_pct: float
    amount: float = 0.0
    turnover_rate: float | None = None
    advance: int | None = None
    decline: int | None = None
    flat: int | None = None


async def _quotes_from_tencent(client: httpx.AsyncClient, refs: Sequence[IndexRef]) -> list[Quote]:
    """Tencent's batch quote answers GBK-delimited rows.

    field layout: 1=name 2=code 3=price 31=change 32=changePct 35=price/vol/amount
    37=amount(万元) 38=turnover. It is the primary path because the whole
    eastmoney push2 cluster has historically been unreachable.
    """
    symbols = ",".join(ref.tx for ref in refs)
    text = await fetch_text(client, f"https://qt.gtimg.cn/q={symbols}", "https://gu.qq.com/", "gbk")
    by_code: dict[str, Quote] = {}
    for match in re.finditer(r'v_([a-z]{2})(\d{6})="([^"]*)"', text):
        fields = match.group(3).split("~")
        if len(fields) < 39:
            continue  # v_pv_none_match="1" and empty placeholders
        legs = (fields[35] if len(fields) > 35 else "").split("/")
        code = fields[2] or match.group(2)
        amount = num(legs[2]) if len(legs) > 2 else 0.0
        if not amount and len(fields) > 37:
            amount = num(fields[37]) * 1e4
        by_code[code] = Quote(
            code=code,
            name=fields[1],
            price=num(fields[3]),
            change=rnd(num(fields[31])),
            change_pct=rnd(num(fields[32])),
            amount=amount,
            turnover_rate=None if len(fields) <= 38 or fields[38] == "" else rnd(num(fields[38])),
        )
    return [by_code[ref.code] for ref in refs if ref.code in by_code]


async def _quotes_from_push2(client: httpx.AsyncClient, refs: Sequence[IndexRef]) -> list[Quote]:
    """Walk the numbered mirrors until one answers with rows."""
    global _quotes_cursor, last_quote_host
    secids = ",".join(ref.secid for ref in refs)
    fields = "f1,f2,f3,f4,f6,f8,f12,f13,f14,f104,f105,f106"
    last_error: UpstreamError = UpstreamError("upstream_no_host")
    for step in range(len(PUSH2_HOSTS)):
        index = (_quotes_cursor + step) % len(PUSH2_HOSTS)
        host = PUSH2_HOSTS[index]
        url = (
            f"https://{host}/api/qt/ulist.np/get?fltt=2"
            f"&secids={secids}&fields={fields}"
        )
        try:
            payload = await fetch_json(client, url, "https://quote.eastmoney.com/")
            rows: list = (payload.get("data") or {}).get("diff") or []
            if not rows:
                raise UpstreamError("upstream_empty_diff", host)
            _quotes_cursor = index
            last_quote_host = host
            return [
                Quote(
                    code=str(row.get("f12", "")),
                    name=str(row.get("f14") or ""),
                    price=num(row.get("f2")),
                    change=rnd(num(row.get("f4"))),
                    change_pct=rnd(num(row.get("f3"))),
                    amount=num(row.get("f6")),
                    turnover_rate=None
                    if row.get("f8") in (None, "-", "")
                    else rnd(num(row.get("f8"))),
                    advance=int(num(row.get("f104"))),
                    decline=int(num(row.get("f105"))),
                    flat=int(num(row.get("f106"))),
                )
                for row in rows
            ]
        except UpstreamError as exc:
            last_error = exc
    raise last_error


async def fetch_index_quotes(
    client: httpx.AsyncClient, codes: Sequence[str] | None = None
) -> tuple[list[Quote], str]:
    """Realtime index quotes: Tencent first, push2 mirrors as backup.

    Returns ``(rows, source)`` where ``source`` names the host that actually
    served the batch — the disclosure research-terminal's ``runtime.quoteHost``
    makes on every health check.
    """
    wanted = [c for c in (codes or INDEX_CODES) if c in INDEX_UNIVERSE]
    if not wanted:
        wanted = list(INDEX_CODES)
    refs = [INDEX_UNIVERSE[c] for c in wanted]

    first_error: UpstreamError = UpstreamError("upstream_empty_quote")
    try:
        rows = await _quotes_from_tencent(client, refs)
        if rows:
            return _ordered(rows, wanted), "qt.gtimg.cn"
    except UpstreamError as exc:
        first_error = exc

    try:
        rows = await _quotes_from_push2(client, refs)
        if rows:
            return _ordered(rows, wanted), last_quote_host
    except UpstreamError as exc:
        raise UpstreamError(
            f"upstream_quote_{first_error.code.strip()}_{exc.code.strip()}"[:90]
        ) from exc

    raise UpstreamError(f"upstream_quote_{first_error.code.strip()}"[:90])


def _ordered(rows: Iterable[Quote], codes: Sequence[str]) -> list[Quote]:
    """Upstreams reorder or drop entries; answer in the requested order."""
    by_code = {row.code: row for row in rows}
    return [by_code[c] for c in codes if c in by_code]


# --- daily bars --------------------------------------------------------------

@dataclass
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class BarsResult:
    bars: list[Bar]
    source: str  # tencent | sina | sina_unadjusted
    as_of: str

    @property
    def available(self) -> bool:
        return bool(self.bars)


async def fetch_daily_bars(
    client: httpx.AsyncClient, tx_symbol: str, sina_symbol: str, days: int, adjust: bool = True
) -> BarsResult:
    """Daily K-line: Tencent first (supports qfq), Sina as backup.

    Sina has no forward adjustment, so when it serves a request that asked for
    ``qfq`` the source must read ``sina_unadjusted`` — a caller is never told an
    unadjusted series is adjusted.
    """
    bars = await _tencent_bars(client, tx_symbol, days, adjust)
    if len(bars) > 1:
        return BarsResult(bars, "tencent", bars[-1].date)

    sina = await _sina_bars(client, sina_symbol, days)
    if len(sina) > len(bars):
        return BarsResult(sina, "sina_unadjusted" if adjust else "sina", sina[-1].date)
    if bars:
        return BarsResult(bars, "tencent", bars[-1].date)
    raise UpstreamError("no_bars")


async def _tencent_bars(client: httpx.AsyncClient, symbol: str, days: int, adjust: bool) -> list[Bar]:
    kind = "qfq" if adjust else ""
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?param={symbol},day,,,{days},{kind}"
    )
    payload = await fetch_json(client, url, "https://gu.qq.com/")
    node = (payload.get("data") or {}).get(symbol) or {}
    raw = node.get("day") or node.get("qfqday") or []
    bars: list[Bar] = []
    for row in raw:
        if not isinstance(row, (list, tuple)) or len(row) < 6:
            continue
        day = str(row[0])
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", day):
            continue
        close = num(row[2])
        if close <= 0:
            continue
        bars.append(Bar(day, num(row[1]), num(row[3]), num(row[4]), close, num(row[5])))
    return bars


async def _sina_bars(client: httpx.AsyncClient, symbol: str, days: int) -> list[Bar]:
    url = (
        "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        f"CN_MarketData.getKLineData?symbol={symbol}&scale=240&ma=no&datalen={days}"
    )
    payload = await fetch_json(client, url, "https://finance.sina.com.cn/")
    bars: list[Bar] = []
    if not isinstance(payload, list):
        return bars
    for row in payload:
        day = str(row.get("day", ""))
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", day) or num(row.get("close")) <= 0:
            continue
        bars.append(
            Bar(day, num(row.get("open")), num(row.get("high")), num(row.get("low")),
                num(row.get("close")), num(row.get("volume")))
        )
    return bars


async def fetch_index_bars(
    client: httpx.AsyncClient, code: str, days: int = 260, adjust: bool = True
) -> BarsResult:
    ref = INDEX_UNIVERSE.get(code)
    if ref is None:
        raise UpstreamError("invalid_index_code")
    return await fetch_daily_bars(client, ref.tx, ref.sina, days, adjust)


# --- calendar helpers --------------------------------------------------------

def latest_trade_date(today: date | None = None) -> str:
    """The most recent session that has closed (before 09:30 → previous day).

    Mirrors research-terminal's ``tradeDate()`` so an empty intraday pool is
    never reported as today's.
    """
    now = datetime.now(timezone(timedelta(hours=8))).date() if today is None else today
    if now.weekday() >= 5:
        now -= timedelta(days=now.weekday() - 4)
    hour = datetime.now(timezone(timedelta(hours=8))).hour
    minute = datetime.now(timezone(timedelta(hours=8))).minute
    if today is None and (hour < 9 or (hour == 9 and minute < 30)):
        now -= timedelta(days=1)
        while now.weekday() >= 5:
            now -= timedelta(days=1)
    return now.isoformat()


def is_stale(as_of: str, max_age_days: int = 3) -> tuple[bool, int]:
    """Whether a business date has fallen behind, and by how many calendar days.

    Used to turn "we answered" into "we answered with current data".
    """
    if not as_of:
        return True, -1
    try:
        parsed = date.fromisoformat(str(as_of)[:10])
    except ValueError:
        return True, -1
    age = (date.today() - parsed).days
    return age > max_age_days, age


# --- live metric feeds -------------------------------------------------------

@dataclass
class SeriesResult:
    """A dated numeric series plus the date the market printed it."""

    points: list[dict]
    source: str
    as_of: str

    @property
    def latest(self) -> dict | None:
        return self.points[-1] if self.points else None


#: legulegu publishes PE/PB for these names only; anything else has no live
#: valuation feed and must be declared unavailable rather than guessed.
LG_INDEX_SYMBOLS: dict[str, str] = {
    "000016": "上证50",
    "000300": "沪深300",
    "000905": "中证500",
    "000852": "中证1000",
    "000903": "中证100",
    "000906": "中证800",
}


async def fetch_index_pe(index_code: str) -> SeriesResult:
    """Live index PE(TTM) series from legulegu.

    The value used is the upstream's own ``滚动市盈率`` (TTM) column — never a
    static default.  A missing symbol raises rather than inventing a level.
    """
    symbol = LG_INDEX_SYMBOLS.get(index_code)
    if symbol is None:
        raise UpstreamError("unavailable_index_valuation")

    import akshare as ak

    frame = await run_ak(lambda: ak.stock_index_pe_lg(symbol=symbol), timeout=15.0)
    if frame is None or frame.empty:
        raise UpstreamError("upstream_empty", "legulegu.com")

    date_col = "日期"
    ttm_col = "滚动市盈率" if "滚动市盈率" in frame.columns else None
    if ttm_col is None:
        raise UpstreamError("upstream_missing_column", "legulegu.com")

    points = []
    for _, row in frame.iterrows():
        day = row.get(date_col)
        value = row.get(ttm_col)
        if value is None or value != value:
            continue
        points.append({"date": str(day), "pe_ttm": float(value)})
    if not points:
        raise UpstreamError("upstream_empty", "legulegu.com")
    return SeriesResult(points, "legulegu.com", points[-1]["date"])


async def fetch_index_pb(index_code: str) -> SeriesResult:
    symbol = LG_INDEX_SYMBOLS.get(index_code)
    if symbol is None:
        raise UpstreamError("unavailable_index_valuation")

    import akshare as ak

    frame = await run_ak(lambda: ak.stock_index_pb_lg(symbol=symbol), timeout=15.0)
    if frame is None or frame.empty or "市净率" not in frame.columns:
        raise UpstreamError("upstream_empty", "legulegu.com")
    points = [
        {"date": str(row["日期"]), "pb": float(row["市净率"])}
        for _, row in frame.iterrows()
        if row.get("市净率") == row.get("市净率")
    ]
    if not points:
        raise UpstreamError("upstream_empty", "legulegu.com")
    return SeriesResult(points, "legulegu.com", points[-1]["date"])


async def fetch_treasury_yields(start: str, end: str) -> SeriesResult:
    """China Government Bond yield curve, newest first, from chinamoney.

    ``bond_china_yield``'s upstream defaults ``end_date`` to 2021-01-24, so the
    window must always be pinned explicitly or it silently comes back empty.
    """
    import akshare as ak

    frame = await run_ak(
        lambda: ak.bond_china_yield(start_date=start, end_date=end), timeout=15.0
    )
    if frame is None or frame.empty:
        raise UpstreamError("upstream_empty", "www.chinamoney.com.cn")
    points = [
        {
            "date": str(row["日期"]),
            "curve": str(row.get("曲线名称", "")),
            "y1": row.get("1年"),
            "y3": row.get("3年"),
            "y5": row.get("5年"),
            "y10": row.get("10年"),
            "y30": row.get("30年"),
        }
        for _, row in frame.iterrows()
    ]
    points = [p for p in points if p["date"]]
    if not points:
        raise UpstreamError("upstream_empty", "www.chinamoney.com.cn")
    return SeriesResult(points, "www.chinamoney.com.cn", points[-1]["date"])


async def fetch_margin_balance(start: str, end: str) -> SeriesResult:
    """SSE two-margin balance — the leverage factor's live input."""
    import akshare as ak

    frame = await run_ak(
        lambda: ak.stock_margin_sse(start_date=start, end_date=end), timeout=15.0
    )
    if frame is None or frame.empty:
        raise UpstreamError("upstream_empty", "www.sse.com.cn")
    points = [
        {"date": str(row["信用交易日期"]), "balance": float(row["融资融券余额"])}
        for _, row in frame.iterrows()
        if str(row.get("信用交易日期", "")) and row.get("融资融券余额") == row.get("融资融券余额")
    ]
    if not points:
        raise UpstreamError("upstream_empty", "www.sse.com.cn")
    points.sort(key=lambda p: p["date"])
    return SeriesResult(points, "www.sse.com.cn", points[-1]["date"])


async def fetch_futures_daily(symbol: str = "IF0") -> SeriesResult:
    """Main continuous futures contract daily bars (Sina)."""
    import akshare as ak

    frame = await run_ak(lambda: ak.futures_zh_daily_sina(symbol=symbol), timeout=15.0)
    if frame is None or frame.empty or "close" not in frame.columns:
        raise UpstreamError("upstream_empty", "vip.stock.finance.sina.com.cn")
    points = [
        {"date": str(row["date"]), "close": float(row["close"]), "volume": float(row.get("volume", 0) or 0)}
        for _, row in frame.iterrows()
        if row.get("close") == row.get("close") and float(row.get("close", 0) or 0) > 0
    ]
    if not points:
        raise UpstreamError("upstream_empty", "vip.stock.finance.sina.com.cn")
    return SeriesResult(points, "vip.stock.finance.sina.com.cn", points[-1]["date"])


async def fetch_treasury_daily(start: str) -> list[dict]:
    """Daily 10-year China government yield from ``bond_zh_us_rate``.

    ``bond_china_yield`` only answers with a handful of rows however wide the
    window, which is not enough to walk a monthly valuation history.  This feed
    is genuinely daily and carries the 10-year tenor directly.
    """
    import akshare as ak

    frame = await run_ak(lambda: ak.bond_zh_us_rate(start_date=start), timeout=15.0)
    if frame is None or frame.empty:
        raise UpstreamError("upstream_empty", "www.chinamoney.com.cn")
    col = next((c for c in frame.columns if "中国国债收益率10年" in str(c)), None)
    if col is None:
        raise UpstreamError("upstream_missing_column", "www.chinamoney.com.cn")
    points = []
    for _, row in frame.iterrows():
        value = row.get(col)
        day = str(row.get("日期", ""))
        if value is None or value != value or not day:
            continue
        points.append({"date": day, "y10": float(value)})
    if not points:
        raise UpstreamError("upstream_empty", "www.chinamoney.com.cn")
    return points


async def fetch_money_market_rates() -> SeriesResult:
    """Live SHIBOR tenors, newest first, from the interbank fixing.

    Replaces the frozen ``money_market_rates`` table, whose ``rate_code``
    column held random numeric strings and whose ``rate_value`` was a constant
    2.0 for every row.  One point per session carrying all published tenors.
    """
    import akshare as ak

    frame = await run_ak(lambda: ak.macro_china_shibor_all(), timeout=15.0)
    if frame is None or frame.empty:
        raise UpstreamError("upstream_empty", "www.shibor.org")

    tenor_columns = [
        ("O/N", "O/N-定价"),
        ("1W", "1W-定价"),
        ("2W", "2W-定价"),
        ("1M", "1M-定价"),
        ("3M", "3M-定价"),
        ("6M", "6M-定价"),
        ("9M", "9M-定价"),
        ("1Y", "1Y-定价"),
    ]
    points: list[dict] = []
    for _, row in frame.iterrows():
        day = str(row.get("日期", ""))
        if not day:
            continue
        point: dict = {"date": day}
        for code, column in tenor_columns:
            value = row.get(column)
            if value is not None and value == value:
                point[code] = float(value)
        if len(point) > 1:
            points.append(point)
    if not points:
        raise UpstreamError("upstream_empty", "www.shibor.org")
    points.sort(key=lambda p: p["date"])
    return SeriesResult(points, "www.shibor.org", points[-1]["date"])


async def fetch_sw_industries() -> SeriesResult:
    """31 Shenwan level-1 industries with live TTM PE / PB / dividend yield.

    This is the only sector valuation feed reachable from here — the East Money
    board endpoints all sit on the dead push2 cluster.  Its as-of is the day the
    index company published it.
    """
    import akshare as ak

    frame = await run_ak(lambda: ak.sw_index_first_info(), timeout=15.0)
    if frame is None or frame.empty:
        raise UpstreamError("upstream_empty", "www.swindex.cn")
    pe_col = "TTM(滚动)市盈率" if "TTM(滚动)市盈率" in frame.columns else None
    if pe_col is None:
        raise UpstreamError("upstream_missing_column", "www.swindex.cn")
    points = []
    for _, row in frame.iterrows():
        name = str(row.get("行业名称", "")).strip()
        if not name:
            continue
        points.append(
            {
                "asset_code": name,
                "sw_code": str(row.get("行业代码", "")),
                "category": "sector",
                "pe_ttm": float(row[pe_col]) if row.get(pe_col) == row.get(pe_col) else None,
                "pb": float(row["市净率"]) if row.get("市净率") == row.get("市净率") else None,
                "dividend_yield": float(row["静态股息率"])
                if row.get("静态股息率") == row.get("静态股息率")
                else None,
                "constituents": int(row["成份个数"]) if row.get("成份个数") else None,
            }
        )
    if not points:
        raise UpstreamError("upstream_empty", "www.swindex.cn")
    return SeriesResult(points, "www.swindex.cn", latest_trade_date())


async def fetch_margin_series(start: str, end: str) -> SeriesResult:
    """SSE two-margin balance history — the leverage factor's live input."""
    import akshare as ak

    frame = await run_ak(
        lambda: ak.macro_china_market_margin_sh(), timeout=15.0
    )
    if frame is None or frame.empty or "融资融券余额" not in frame.columns:
        raise UpstreamError("upstream_empty", "www.sse.com.cn")
    points = [
        {"date": str(row["日期"]), "balance": float(row["融资融券余额"])}
        for _, row in frame.iterrows()
        if str(row.get("日期", "")) and row.get("融资融券余额") == row.get("融资融券余额")
    ]
    points = [p for p in points if p["date"] >= start]
    if not points:
        raise UpstreamError("upstream_empty", "www.sse.com.cn")
    points.sort(key=lambda p: p["date"])
    return SeriesResult(points, "www.sse.com.cn", points[-1]["date"])


# --- upstream health probe ---------------------------------------------------

@dataclass
class Probe:
    id: str
    label: str
    status: str  # up | empty | down
    ms: int
    records: int = 0
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Serialisable form for ``/api/health?probes=true``."""
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "ms": self.ms,
            "records": self.records,
            "error": self.error,
        }


#: (id, label, coroutine factory) — one entry per upstream research-terminal
#: probes in ``action=health``.  Alphaplus gains the same self-evidence.
HEALTH_TARGETS: list[tuple[str, str, Callable[[httpx.AsyncClient], Any]]] = []

#: Human labels for each probe id, kept beside registration so a probe cannot
#: be added without a label the health payload can render.
PROBE_LABELS: dict[str, str] = {
    "tencent": "腾讯行情 qt.gtimg.cn",
    "push2": "东方财富 push2",
    "push2ex_breadth": "东方财富 push2ex 市场宽度",
    "tencent_bars": "腾讯日线",
    "sina_bars": "新浪日线 (备用源)",
    "sina_quotes": "新浪报价",
    "chinamoney": "中国外汇交易中心 chinamoney",
    "legulegu": "乐咕乐股 指数 PE",
}


def _reg(
    target: tuple[str, str, Callable[[httpx.AsyncClient], Any]]
    | Callable[[httpx.AsyncClient], Any],
) -> tuple[str, str, Callable[[httpx.AsyncClient], Any]] | Callable:
    """Register a probe as ``(id, label, factory)``.

    Accepts either the explicit 3-tuple or a bare coroutine factory decorated
    as ``@_reg``.  The bare form used to append the raw function while
    ``probe_upstreams()`` unpacked three items, so ``/api/health?probes=true``
    died with ``TypeError: 'function' object is not subscriptable``.  Returning
    the original function keeps the decorated name callable.
    """
    if isinstance(target, tuple):
        HEALTH_TARGETS.append(target)
        return target
    probe_id = target.__name__.removeprefix("_probe_")
    entry = (probe_id, PROBE_LABELS.get(probe_id, probe_id), target)
    HEALTH_TARGETS.append(entry)
    return target


@_reg
async def _probe_tencent(client: httpx.AsyncClient) -> list[Quote]:
    rows, _ = await fetch_index_quotes(client, ["000300"])
    return rows


@_reg
async def _probe_push2(client: httpx.AsyncClient) -> list[Quote]:
    rows = await _quotes_from_push2(client, [INDEX_UNIVERSE["000300"]])
    return rows


@_reg
async def _probe_push2ex_breadth(client: httpx.AsyncClient) -> list[Breadth]:
    return [await fetch_breadth(client)]


@_reg
async def _probe_tencent_bars(client: httpx.AsyncClient) -> list[Bar]:
    result = await fetch_daily_bars(client, "sh000300", "sh000300", 10, adjust=False)
    return result.bars


@_reg
async def _probe_sina_bars(client: httpx.AsyncClient) -> list[Bar]:
    # bj899050 is the case Tencent only ever answers with one bar, so this is
    # the path that proves Sina backup really works.
    result = await fetch_daily_bars(client, "bj899050", "bj899050", 10, adjust=False)
    return result.bars


@_reg
async def _probe_sina_quotes(client: httpx.AsyncClient) -> list[Quote]:
    url = (
        "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        "Market_Center.getHQNodeData?page=1&num=5&sort=changepercent&asc=0&node=hs_a"
    )
    payload = await fetch_json(client, url, "https://finance.sina.com.cn/")
    if not isinstance(payload, list):
        raise UpstreamError("upstream_bad_json", "vip.stock.finance.sina.com.cn")
    return payload


@_reg
async def _probe_chinamoney(client: httpx.AsyncClient) -> list[Any]:
    url = "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json"
    payload = await fetch_json(client, url)
    records = payload.get("records") or []
    if not records:
        raise UpstreamError("upstream_empty", "www.chinamoney.com.cn")
    return records


@_reg
async def _probe_legulegu(client: httpx.AsyncClient) -> list[Any]:
    # Legulegu needs a daily token minted in JS; the akshare call owns that.
    result = await fetch_index_pe("000300")
    return [result.latest] if result.latest else []


async def probe_upstreams() -> list[Probe]:
    """Probe every upstream and report latency — the proof that data is live."""
    results: list[Probe] = []
    # Same client policy as live_feed.upstream_client (trust_env=False): a
    # shell-exported proxy must not reroute the probes, and an unsupported
    # proxy scheme must not be able to 500 the health endpoint itself.
    # A health probe must never raise: if the client cannot even be built,
    # every target is reported down rather than the endpoint erroring.
    try:
        client_ctx = httpx.AsyncClient(
            timeout=15.0, follow_redirects=True, verify=True, trust_env=False
        )
    except Exception:  # noqa: BLE001
        return [
            Probe(pid, label, "down", 0, error="probe_client_init_failed")
            for pid, label, _ in HEALTH_TARGETS
        ]
    async with client_ctx as client:
        async def one(probe_id: str, label: str, factory: Callable) -> Probe:
            started = datetime.now(timezone.utc)
            try:
                value = await factory(client)
                count = len(value) if isinstance(value, (list, dict)) else 1
                ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
                return Probe(
                    probe_id, label, "up" if count else "empty", ms, records=count
                )
            except Exception as exc:  # noqa: BLE001 - a probe must never raise
                ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
                code = exc.code if isinstance(exc, UpstreamError) else "runtime_" + type(exc).__name__
                return Probe(probe_id, label, "down", ms, error=code)

        probes = [one(pid, label, factory) for pid, label, factory in HEALTH_TARGETS]
        results = list(await asyncio.gather(*probes))
    return results
