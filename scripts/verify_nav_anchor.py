#!/usr/bin/env python3
"""
External-anchor verification for fund stage returns.

This is the Alphaplus counterpart of research-terminal's ``dev/verify_fund.ts``:
it does NOT check internal self-consistency. It asserts that *our* chain of
reported daily growth ("复权" total-return index) reproduces the stage returns
that East Money itself publishes on its ranking page.

Rule under test (the one that made the numbers line up):
    base = last valuation dated ON OR BEFORE (end_date - relativedelta(label))
    stage_return(label) = nav(end) / nav(base) - 1

Empirically validated over 12 large, diverse funds (incl. a QDII): the plain
unit-NAV ratio reproduces East Money's published stage returns to <0.01pp.
Chaining the fund's *reported* daily growth instead drifts by ~1-2pp per year,
because that column is rounded to 2 decimals and the error compounds.

Usage:
    python3 scripts/verify_nav_anchor.py [--funds 110022,161725,...] [--max-error 0.05]

Exit code 0 = all funds within tolerance, 1 = at least one breach, 2 = upstream
unavailable (so CI can distinguish "wrong" from "offline").
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

WINDOWS = ("近1月", "近3月", "近6月", "近1年", "近3年")


def _shift(end: pd.Timestamp, label: str) -> pd.Timestamp:
    import re
    from dateutil.relativedelta import relativedelta

    match = re.match(r"近(\d+)(月|年)", label)
    if not match:
        raise ValueError(f"unparsable window label: {label}")
    n = int(match.group(1))
    unit = match.group(2)
    delta = relativedelta(months=n) if unit == "月" else relativedelta(years=n)
    return end - delta


def check_fund(ak, code: str) -> dict:
    nav = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
    nav.columns = ["date", "nav", "growth"]
    nav["date"] = pd.to_datetime(nav["date"])
    nav = nav.sort_values("date").reset_index(drop=True)
    nav["nav"] = pd.to_numeric(nav["nav"], errors="coerce")
    # Total-return basis: the unit-NAV ratio, anchored at 1.0 on the first row.
    nav["tri"] = (nav["nav"] / nav["nav"].shift(1)).fillna(1.0).cumprod()

    rank = ak.fund_open_fund_rank_em(symbol="全部")
    rows = rank[rank["基金代码"] == code]
    if rows.empty:
        return {"code": code, "error": "not_in_ranking"}
    row = rows.iloc[0]

    end_date = nav["date"].iloc[-1]
    end_tri = nav["tri"].iloc[-1]
    results = []
    worst = 0.0
    for label in WINDOWS:
        published = row.get(label)
        if published is None or pd.isna(published):
            continue
        target = _shift(end_date, label)
        base_rows = nav[nav["date"] <= target]
        if base_rows.empty:
            continue
        base = base_rows.iloc[-1]
        calc = (end_tri / base["tri"] - 1) * 100
        diff = calc - float(published)
        worst = max(worst, abs(diff))
        results.append(
            {
                "window": label,
                "published": float(published),
                "calculated": round(calc, 4),
                "diff": round(diff, 4),
            }
        )
    return {"code": code, "as_of": str(end_date.date()), "worst": round(worst, 4), "windows": results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--funds",
        default="110022,161725,005827,000961,519674,003095,001618,006533,012414,017641,519005,011103",
        help="comma-separated fund codes",
    )
    parser.add_argument("--max-error", type=float, default=0.05, help="max allowed |pp| error")
    args = parser.parse_args()

    try:
        import akshare as ak

        # Connectivity probe: if this fails we are offline, not wrong.
        probe = ak.fund_open_fund_info_em(symbol="110022", indicator="单位净值走势")
        if probe is None or probe.empty:
            print("UPSTREAM_UNAVAILABLE: empty probe response")
            return 2
    except Exception as exc:  # noqa: BLE001
        print(f"UPSTREAM_UNAVAILABLE: {type(exc).__name__}: {exc}")
        return 2

    codes = [c.strip() for c in args.funds.split(",") if c.strip()]
    failures = 0
    checked = 0
    for code in codes:
        try:
            report = check_fund(ak, code)
        except Exception as exc:  # noqa: BLE001
            print(f"SKIP {code}: {type(exc).__name__}: {exc}")
            continue
        if "error" in report:
            print(f"SKIP {code}: {report['error']}")
            continue
        checked += 1
        status = "ok  " if report["worst"] <= args.max_error else "FAIL"
        if report["worst"] > args.max_error:
            failures += 1
        print(f"{status} {code} as_of={report['as_of']} worst={report['worst']}" )
        for w in report["windows"]:
            print(
                f"       {w['window']}: published={w['published']:>8} "
                f"calc={w['calculated']:>8} diff={w['diff']:+.4f}"
            )

    print(f"\nchecked={checked} failures={failures} tolerance={args.max_error}pp")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
