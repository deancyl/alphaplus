#!/usr/bin/env python3
"""
Verify the LLM interpretation layer against a local mock of the OpenAI API.

Checks both wire formats the client supports:
  * chat      -> POST /v1/chat/completions
  * responses -> POST /v1/responses

This is a *contract* test: it proves we send a well-formed request, parse the
answer, and (separately) that with no key configured we degrade honestly.

Usage:
    python3 scripts/verify_llm.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0])

CAPTURED: dict = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence
        pass

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        CAPTURED["path"] = self.path
        CAPTURED["body"] = body
        CAPTURED["auth"] = self.headers.get("Authorization")

        if self.path.endswith("/chat/completions"):
            payload = {
                "choices": [{"message": {"role": "assistant", "content": "CHAT_OK: 走势判断..."}}],
                "usage": {"total_tokens": 12},
            }
        elif self.path.endswith("/responses"):
            payload = {
                "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": "RESP_OK: 走势判断..."}]}
                ],
                "output_text": "RESP_OK: 走势判断...",
                "usage": {"total_tokens": 12},
            }
        else:
            self.send_response(404)
            self.end_headers()
            return

        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _run_server(port: int) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


async def _main() -> int:
    from backend.core.config import settings
    from backend.services.llm_client import analyse_forecast

    port = 8231
    server = _run_server(port)
    failures = []

    try:
        # --- chat format ---
        settings.llm_base_url = f"http://127.0.0.1:{port}/v1"
        settings.llm_api_key = "test-key"
        settings.llm_api_style = "chat"
        settings.llm_model = "mock-model"

        result = await analyse_forecast({"index_name": "沪深300", "last_close": 4166.0})
        if not result.available or "CHAT_OK" not in (result.text or ""):
            failures.append(f"chat format failed: {result.to_dict()}")
        if not CAPTURED.get("path", "").endswith("/chat/completions"):
            failures.append(f"chat did not POST to /chat/completions: {CAPTURED.get('path')}")
        if CAPTURED.get("auth") != "Bearer test-key":
            failures.append(f"bad auth header: {CAPTURED.get('auth')}")
        if "messages" not in CAPTURED.get("body", {}):
            failures.append("chat body missing messages[]")
        print("chat      :", "OK" if result.available else "FAIL", "->", result.text)

        # --- responses format ---
        settings.llm_api_style = "responses"
        result = await analyse_forecast({"index_name": "沪深300", "last_close": 4166.0})
        if not result.available or "RESP_OK" not in (result.text or ""):
            failures.append(f"responses format failed: {result.to_dict()}")
        if not CAPTURED.get("path", "").endswith("/responses"):
            failures.append(f"responses did not POST to /responses: {CAPTURED.get('path')}")
        if "input" not in CAPTURED.get("body", {}):
            failures.append("responses body missing input")
        print("responses :", "OK" if result.available else "FAIL", "->", result.text)

        # --- no key -> honest ---
        settings.llm_api_key = None
        result = await analyse_forecast({"index_name": "x"})
        if result.enabled or result.error != "llm_not_configured":
            failures.append(f"no-key degradation wrong: {result.to_dict()}")
        print("no-key    :", "OK" if result.error == "llm_not_configured" else "FAIL")
    finally:
        server.shutdown()

    if failures:
        print("\nFAIL")
        for f in failures:
            print(" -", f)
        return 1
    print("\nPASS: LLM chat + responses formats and honest no-key degradation")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
