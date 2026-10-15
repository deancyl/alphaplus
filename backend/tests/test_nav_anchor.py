"""
External-anchor acceptance test for the NAV/stage-return caliber.

Mirrors research-terminal's ``dev/verify_fund.ts``: it does not test internal
self-consistency, it tests whether our computed stage returns reproduce the
numbers East Money publishes. Network-gated: skips (rather than fails) when the
upstream is unreachable, so CI distinguishes "offline" from "wrong".
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

WINDOWS = ("近1月", "近3月", "近6月", "近1年", "近3年")
TOLERANCE_PP = 0.05
FUNDS = ["110022", "161725", "005827", "000961", "519674", "003095"]


def _shift(end: pd.Timestamp, label: str) -> pd.Timestamp:
    from dateutil.relativedelta import relativedelta

    match = re.match(r"近(\d+)(月|年)", label)
    n = int(match.group(1))
    delta = relativedelta(months=n) if match.group(2) == "月" else relativedelta(years=n)
    return end - delta


@pytest.fixture(scope="module")
def ak():
    try:
        import akshare as ak_module

        probe = ak_module.fund_open_fund_info_em(symbol="110022", indicator="单位净值走势")
        if probe is None or probe.empty:
            pytest.skip("upstream unavailable: empty probe")
        return ak_module
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"upstream unavailable: {type(exc).__name__}: {exc}")


@pytest.mark.parametrize("code", FUNDS)
def test_stage_returns_match_eastmoney(ak, code):
    nav = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
    nav.columns = ["date", "nav", "growth"]
    nav["date"] = pd.to_datetime(nav["date"])
    nav = nav.sort_values("date").reset_index(drop=True)
    nav["nav"] = pd.to_numeric(nav["nav"], errors="coerce")
    nav["tri"] = (nav["nav"] / nav["nav"].shift(1)).fillna(1.0).cumprod()

    rank = ak.fund_open_fund_rank_em(symbol="全部")
    rows = rank[rank["基金代码"] == code]
    if rows.empty:
        pytest.skip(f"{code} not in ranking")
    row = rows.iloc[0]

    end_date = nav["date"].iloc[-1]
    end_tri = nav["tri"].iloc[-1]

    # The ranking page and the NAV series are two *different* upstream feeds
    # that roll over to a new trading day at different times. Comparing them
    # across an as-of gap would manufacture a false caliber breach, so we
    # require both sides to speak about the same date.
    rank_date = pd.to_datetime(row.get("日期"))
    if pd.notna(rank_date) and end_date < rank_date:
        pytest.skip(
            f"{code} as-of mismatch: rank page as of {rank_date.date()} "
            f"but NAV series ends {end_date.date()} (upstream lag)"
        )

    checked = 0
    for label in WINDOWS:
        published = row.get(label)
        if published is None or pd.isna(published):
            continue
        base_rows = nav[nav["date"] <= _shift(end_date, label)]
        if base_rows.empty:
            continue
        base = base_rows.iloc[-1]
        calc = (end_tri / base["tri"] - 1) * 100
        diff = abs(calc - float(published))
        assert diff <= TOLERANCE_PP, (
            f"{code} {label}: published={published} calc={calc:.4f} diff={diff:.4f}pp"
        )
        checked += 1
    assert checked > 0, f"{code}: no comparable windows"
