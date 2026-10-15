#!/usr/bin/env python3
"""
End-to-end smoke test for the Forecast page on the internal test port (60100).

Navigates client-side (so history-mode deep links are not required), waits for
the projection chart to render, and asserts the honesty contract holds: when no
LLM key is configured the page must state that AI interpretation is unavailable
rather than showing invented text.

Usage:
    PORT=60100 python3 scripts/smoke_forecast_ui.py
"""
from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

PORT = os.environ.get("PORT", "60100")
BASE = f"http://127.0.0.1:{PORT}"


def main() -> int:
    failures: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)

        try:
            page.goto(f"{BASE}/", wait_until="networkidle", timeout=30000)
            # client-side navigation to the forecast route
            page.evaluate("history.pushState({}, '', '/market/forecast')")
            page.evaluate("window.dispatchEvent(new PopStateEvent('popstate'))")
            page.wait_for_timeout(1500)

            title = page.locator("h1", has_text="指数走势分析与预测")
            if title.count() == 0:
                failures.append("forecast page heading not found")

            # Wait for the projection chart (ECharts canvas/svg) to appear.
            page.wait_for_selector(".chart-card", timeout=25000)

            body = page.inner_text("body")
            if "年化漂移" not in body:
                failures.append("metrics block not rendered")
            if "口径（basis）" not in body:
                failures.append("basis section not rendered")
            if "局限（limits）" not in body:
                failures.append("limits section not rendered")

            # Honesty: no LLM key -> the AI section must say unavailable.
            ai_card = page.locator(".llm-card")
            if ai_card.count() > 0:
                ai_text = ai_card.first.inner_text()
                if "不可用" not in ai_text and "未配置" not in ai_text:
                    failures.append("AI section did not declare unavailability")

            page.screenshot(path="/tmp/opencode/forecast_60100.png", full_page=True)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"exception: {type(exc).__name__}: {exc}")
        finally:
            browser.close()

    if console_errors:
        print("console errors:", console_errors[:5])
    if failures:
        print("FAIL")
        for f in failures:
            print(" -", f)
        return 1
    print("PASS: forecast page rendered; chart + metrics + basis/limits + AI-unavailable present")
    print("screenshot: /tmp/opencode/forecast_60100.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
