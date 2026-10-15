"""
OpenAI-compatible LLM client for the forecast *interpretation* layer.

Scope is deliberately narrow (research-terminal principle: the LLM must not be
able to fabricate data):

* The model receives an already-computed, structured forecast and is asked to
  *interpret* it. Numbers come from :mod:`backend.services.forecast`; the model
  is told, in the system prompt, to use only those numbers.
* Both OpenAI API shapes are supported: ``chat`` (``/chat/completions``) and
  ``responses`` (``/responses``). Style is chosen by ``settings.llm_api_style``.
* If no API key is configured the client reports ``enabled=False`` with a
  reason. It never returns a canned/"fake" analysis.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from backend.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是一名量化投研助理。你会收到一个已经计算好的指数走势预测结果（包含漂移、"
    "波动率、Hurst、状态、分位路径带与口径说明）。你的任务只有一个：用中文解读这些"
    "数字的含义与风险。\n"
    "硬性要求：\n"
    "1) 只能引用输入中出现的数字，绝对不要编造或外推任何新的数值。\n"
    "2) 不得给出买卖建议，不得预测具体点位。\n"
    "3) 必须明确指出该预测的局限（历史重采样、无成本假设等）。\n"
    "4) 输出 4 个小节：走势判断、关键依据、风险提示、数据局限。每节 1-3 句。"
)


@dataclass
class LLMResult:
    enabled: bool
    available: bool
    api_style: str
    model: Optional[str]
    text: Optional[str]
    error: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "available": self.available,
            "api_style": self.api_style,
            "model": self.model,
            "text": self.text,
            "error": self.error,
            "usage": self.usage,
        }


def llm_configured() -> bool:
    return bool(settings.llm_api_key)


def _build_user_prompt(forecast_payload: Dict[str, Any]) -> str:
    # Keep the payload compact but complete; the model must not need to guess.
    trimmed = {
        "index": forecast_payload.get("index_name"),
        "as_of": forecast_payload.get("as_of"),
        "last_close": forecast_payload.get("last_close"),
        "horizon_days": forecast_payload.get("horizon_days"),
        "metrics": forecast_payload.get("metrics"),
        "model": forecast_payload.get("model"),
        "expected_band": forecast_payload.get("expected_band"),
        "basis": forecast_payload.get("basis"),
        "limits": forecast_payload.get("limits"),
    }
    return (
        "以下是系统计算出的预测结果（JSON）。请按系统要求解读，不要引入任何新数字：\n"
        + json.dumps(trimmed, ensure_ascii=False)
    )


def _extract_chat_text(body: Dict[str, Any]) -> Optional[str]:
    choices = body.get("choices") or []
    if not choices:
        return None
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    # Some providers return content as a list of parts.
    if isinstance(content, list):
        parts = [p.get("text", "") for p in content if isinstance(p, dict)]
        joined = "".join(parts).strip()
        return joined or None
    return None


def _extract_responses_text(body: Dict[str, Any]) -> Optional[str]:
    # Responses API: prefer the aggregated output_text, else walk output items.
    text = body.get("output_text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    for item in body.get("output") or []:
        if not isinstance(item, dict):
            continue
        for part in item.get("content") or []:
            if isinstance(part, dict) and part.get("type") in ("output_text", "text"):
                value = part.get("text")
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return None


async def analyse_forecast(forecast_payload: Dict[str, Any]) -> LLMResult:
    """Ask the configured LLM to interpret a forecast; degrade honestly."""
    style = (settings.llm_api_style or "chat").lower()
    style = "responses" if style == "responses" else "chat"

    if not llm_configured():
        return LLMResult(
            enabled=False,
            available=False,
            api_style=style,
            model=None,
            text=None,
            error="llm_not_configured",
        )

    base = settings.llm_base_url.rstrip("/")
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    user_prompt = _build_user_prompt(forecast_payload)

    if style == "responses":
        url = f"{base}/responses"
        body: Dict[str, Any] = {
            "model": settings.llm_model,
            "instructions": SYSTEM_PROMPT,
            "input": user_prompt,
            "max_output_tokens": settings.llm_max_output_tokens,
        }
    else:
        url = f"{base}/chat/completions"
        body = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": settings.llm_max_output_tokens,
            "temperature": 0.2,
        }

    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=body)
    except httpx.TimeoutException:
        return LLMResult(True, False, style, settings.llm_model, None, "llm_timeout")
    except httpx.HTTPError as exc:  # network / connection errors
        logger.warning("LLM request failed: %s", exc)
        return LLMResult(True, False, style, settings.llm_model, None, "llm_network_error")

    if response.status_code >= 400:
        # Do not leak provider body text beyond a short, safe suffix.
        detail = ""
        try:
            detail = str(response.json().get("error", {}).get("type", ""))[:40]
        except Exception:
            pass
        return LLMResult(
            True, False, style, settings.llm_model, None,
            f"llm_http_{response.status_code}" + (f"_{detail}" if detail else ""),
        )

    try:
        payload = response.json()
    except ValueError:
        return LLMResult(True, False, style, settings.llm_model, None, "llm_bad_json")

    text = _extract_responses_text(payload) if style == "responses" else _extract_chat_text(payload)
    if not text:
        return LLMResult(True, False, style, settings.llm_model, None, "llm_empty_response")

    return LLMResult(
        enabled=True,
        available=True,
        api_style=style,
        model=settings.llm_model,
        text=text,
        usage=payload.get("usage"),
    )
