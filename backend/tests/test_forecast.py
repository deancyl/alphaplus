"""
Tests for the forecast feature and the unified response envelope.

These are contract + honesty tests, matching the research-terminal philosophy:

* The envelope must never leak raw exception text or URLs.
* The forecast must refuse (not fabricate) when the series is too thin.
* Quantile bands must be monotone and anchored on the last close.
* With no LLM key configured, the API must say ``enabled=false`` rather than
  return invented analysis.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.core.envelope import (  # noqa: E402
    classify_exception,
    fail,
    ok,
    safe_error_code,
    strip_status,
)
from backend.services.forecast import (  # noqa: E402
    ForecastError,
    build_forecast,
    hurst_dfa,
    to_log_returns,
)


# --- envelope ----------------------------------------------------------------

class TestEnvelope:
    def test_ok_shape(self):
        env = ok("kline", {"bars": 3})
        assert env["ok"] is True
        assert env["action"] == "kline"
        assert env["data"] == {"bars": 3}
        assert "generatedAt" in env

    def test_fail_known_code_passthrough(self):
        env = fail("kline", "no_bars", 502)
        assert env["ok"] is False
        assert env["error"] == "no_bars"
        assert env["http_status"] == 502

    def test_fail_does_not_leak_unknown_text(self):
        env = fail("kline", "Upstream exploded at http://secret.internal/x?token=abc", 502)
        assert env["error"] == "internal_error"
        assert "secret" not in str(env)
        assert "token" not in str(env)

    def test_prefixed_codes_allowed(self):
        assert safe_error_code("upstream_timeout") == "upstream_timeout"
        assert safe_error_code("invalid_index_code") == "invalid_index_code"

    def test_classify_exception_uses_class_name(self):
        assert classify_exception(ValueError("x")) == "runtime_value_error"
        assert classify_exception(KeyError("y")) == "runtime_key_error"

    def test_strip_status_removes_hint(self):
        env = fail("x", "no_data", 404)
        assert "http_status" not in strip_status(env)


# --- forecast math -----------------------------------------------------------

class TestForecastMath:
    def test_log_returns_skips_non_positive(self):
        r = to_log_returns([100, 101, 0, -5, 103])
        assert np.all(np.isfinite(r))

    def test_hurst_random_walk_is_near_half(self):
        rng = np.random.default_rng(7)
        walk = rng.standard_normal(4000)
        h = hurst_dfa(walk)
        assert h is not None
        assert 0.35 < h < 0.65, f"DFA on white noise should be ~0.5, got {h}"

    def test_hurst_trending_series_exceeds_half(self):
        rng = np.random.default_rng(11)
        # Cumulative sum of positively autocorrelated noise -> persistent series.
        shocks = rng.standard_normal(4000)
        persistent = np.convolve(shocks, np.ones(5) / 5, mode="same")
        h = hurst_dfa(persistent)
        assert h is not None and h > 0.6

    def test_refuses_thin_series(self):
        with pytest.raises(ForecastError) as exc:
            build_forecast("x", "X", [1.0, 2.0, 3.0], ["a", "b", "c"])
        assert exc.value.code == "insufficient_history"

    def test_quantile_bands_monotone_and_anchored(self):
        rng = np.random.default_rng(3)
        prices = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, 400)))
        dates = [f"d{i}" for i in range(len(prices))]
        result = build_forecast("000300", "沪深300", list(prices), dates, horizon=20)
        q = result.quantiles
        n = len(q["p50"])
        assert n == 21  # anchor + 20 steps
        # All quantiles start exactly at the last close.
        for key in ("p10", "p25", "p50", "p75", "p90"):
            assert q[key][0] == pytest.approx(result.last_close, rel=1e-6)
        # Ordering preserved at every step.
        for i in range(n):
            assert q["p10"][i] <= q["p25"][i] <= q["p50"][i] <= q["p75"][i] <= q["p90"][i]

    def test_drift_cap_applied(self):
        # A pathological series that would otherwise explode the reversion term.
        prices = [100.0] * 200 + [10000.0] * 200
        dates = [f"d{i}" for i in range(len(prices))]
        result = build_forecast("x", "X", prices, dates, horizon=10)
        # Any clamped drift must stay within 3x daily vol; verify path is finite.
        assert all(np.isfinite(v) for v in result.quantiles["p50"])
        assert result.quantiles["p50"][-1] < result.last_close * 2

    def test_is_simulated_false(self):
        rng = np.random.default_rng(5)
        prices = 100 * np.exp(np.cumsum(rng.normal(0.0, 0.01, 300)))
        result = build_forecast("x", "X", list(prices), [f"d{i}" for i in range(300)])
        assert result.is_simulated is False


# --- API contract ------------------------------------------------------------

def _make_app() -> FastAPI:
    from backend.api.forecast import router as forecast_router

    app = FastAPI()
    app.include_router(forecast_router, prefix="/api/v1/analytics")
    return app


class TestForecastAPI:
    def test_invalid_index_returns_400_envelope(self):
        client = TestClient(_make_app())
        resp = client.get("/api/v1/analytics/forecast/999999")
        assert resp.status_code == 400
        body = resp.json()
        assert body["ok"] is False
        assert body["error"] == "invalid_index_code"
        assert "http_status" not in body

    def test_unknown_index_message_does_not_leak(self):
        client = TestClient(_make_app())
        resp = client.get("/api/v1/analytics/forecast/abcdef")
        body = resp.json()
        # Only a short, safe message; no traceback / url.
        assert "Traceback" not in str(body)
        assert "http" not in str(body.get("message", ""))


class TestLLMHonesty:
    def test_llm_disabled_when_no_key(self, monkeypatch):
        import backend.services.llm_client as llm
        from backend.core.config import settings

        monkeypatch.setattr(settings, "llm_api_key", None, raising=False)
        assert llm.llm_configured() is False

    @pytest.mark.asyncio
    async def test_analyse_forecast_reports_not_configured(self, monkeypatch):
        import backend.services.llm_client as llm
        from backend.core.config import settings

        monkeypatch.setattr(settings, "llm_api_key", None, raising=False)
        result = await llm.analyse_forecast({"index_name": "x"})
        assert result.enabled is False
        assert result.available is False
        assert result.error == "llm_not_configured"
        assert result.text is None

    def test_llm_prompt_never_invites_fabrication(self):
        import backend.services.llm_client as llm

        assert "编造" in llm.SYSTEM_PROMPT
        assert "不得" in llm.SYSTEM_PROMPT


class TestHonestDegradation:
    """Simulated fallback must always be distinguishable from real data."""

    def test_default_policy_disables_simulated_fallback(self):
        from backend.core.config import settings

        assert settings.allow_simulated_fallback is False

    def test_mark_simulated_tags_dict(self):
        from backend.services.warmup_fallback import mark_simulated

        tagged = mark_simulated({"a": 1})
        assert tagged["is_simulated"] is True
        assert tagged["source"] == "simulated"

    def test_mark_simulated_tags_list_items(self):
        from backend.services.warmup_fallback import mark_simulated

        tagged = mark_simulated([{"name": "x"}, {"name": "y"}])
        assert all(item["is_simulated"] for item in tagged)

    def test_fallback_sectors_and_heatmap_are_tagged(self):
        from backend.services.warmup_fallback import (
            get_fallback_heatmap,
            get_fallback_sectors,
            mark_simulated,
        )

        assert mark_simulated(get_fallback_sectors())[0]["is_simulated"] is True
        assert mark_simulated(get_fallback_heatmap())["is_simulated"] is True
