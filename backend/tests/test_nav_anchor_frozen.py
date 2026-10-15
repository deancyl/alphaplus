"""
Deterministic external-anchor test for the stage-return caliber.

The live counterpart in this file (``test_stage_returns_match_eastmoney``)
compares two *live* upstream feeds and therefore has to skip whenever they
disagree on the as-of date (rollover lag). This test removes that
nondeterminism: it replays a frozen capture of the raw external inputs —
East Money unit-NAV rows plus East Money's published stage returns — and
asserts that our caliber rule itself

    stage_return(label) = nav(end) / nav(base) - 1,
    base = last valuation on or before end - relativedelta(label)

reproduces the published numbers. Both inputs are external; only the rule is
ours, so this is an anchor test, not a self-consistency test — and it runs
offline.

Fixture: ``fixtures/nav_anchor_frozen.json`` (captured 2026-10-15 while both
feeds agreed on the as-of date).
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "nav_anchor_frozen.json"
TOLERANCE_PP = 0.05


def _shift(end: date, label: str) -> date:
    from dateutil.relativedelta import relativedelta

    match = re.match(r"近(\d+)(月|年)", label)
    n = int(match.group(1))
    delta = relativedelta(months=n) if match.group(2) == "月" else relativedelta(years=n)
    return end - delta


def _load() -> dict:
    if not FIXTURE.exists():
        pytest.skip(f"frozen anchor fixture missing: {FIXTURE.name}")
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


def _cases():
    data = _load()
    for fund in data.get("funds", []):
        for w in fund.get("windows", []):
            yield pytest.param(
                fund["code"], w, id=f"{fund['code']}-{w['window']}"
            )


def test_fixture_is_declared_as_external_capture():
    """The fixture must state provenance — an anchor without provenance is worthless."""
    data = _load()
    assert data.get("source") == "eastmoney"
    assert data.get("captured_at"), "capture date missing"
    assert "published" in data.get("description", "")
    assert data.get("funds"), "no funds captured"


@pytest.mark.parametrize("code,window", list(_cases()))
def test_frozen_stage_return_reproduces_published(code, window):
    from datetime import datetime

    end_date = datetime.strptime(window["end_date"], "%Y-%m-%d").date()
    base_date = datetime.strptime(window["base_date"], "%Y-%m-%d").date()

    # The stored base must actually satisfy the rule (last valuation on or
    # before end - relativedelta(label)); otherwise the fixture is lying.
    target = _shift(end_date, window["window"])
    assert base_date <= target, (
        f"{code} {window['window']}: base {base_date} is after target {target}"
    )

    calc = (window["end_nav"] / window["base_nav"] - 1) * 100
    diff = abs(calc - window["published_pct"])
    assert diff <= TOLERANCE_PP, (
        f"{code} {window['window']}: published={window['published_pct']} "
        f"calc={calc:.4f} diff={diff:.4f}pp"
    )


def test_fixture_covers_multiple_funds_and_windows():
    data = _load()
    funds = data.get("funds", [])
    assert len(funds) >= 2, "anchor must span more than one fund"
    assert all(len(f.get("windows", [])) >= 3 for f in funds)
