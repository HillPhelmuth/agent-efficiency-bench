from __future__ import annotations

import os
from typing import Any

import requests
from pydantic import BaseModel

from agent_efficiency_bench.schemas import ModelConfig


class OpenRouterResponse(BaseModel):
    generation_id: str
    model: str
    content: str
    finish_reason: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    raw: dict[str, Any]


class OpenRouterResponseError(RuntimeError):
    """Raised when OpenRouter returns an unusable HTTP response."""

    pass


class OpenRouterClient:
    def __init__(
        self,
        api_key: str | None = None,
        session: Any | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 120.0,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is required for OpenRouter requests")
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-OpenRouter-Title": os.getenv("OPENROUTER_APP_TITLE", "Agent Efficiency Bench"),
        }
        referer = os.getenv("OPENROUTER_HTTP_REFERER")
        if referer:
            headers["HTTP-Referer"] = referer
        return headers

    def chat(
        self,
        config: ModelConfig,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> OpenRouterResponse:
        request_tools = tools if tools is not None else config.tools
        request_tool_choice = tool_choice if tool_choice is not None else config.tool_choice
        body: dict[str, Any] = {
            "model": config.model,
            "messages": messages,
            "temperature": config.temperature,
            "max_completion_tokens": config.max_completion_tokens,
            **config.extra,
        }
        if config.seed is not None:
            body["seed"] = config.seed
        if request_tools is not None:
            body["tools"] = request_tools
        if request_tool_choice is not None:
            body["tool_choice"] = request_tool_choice

        response = self.session.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=body,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = _json_payload(response, context="OpenRouter chat completion")
        usage = payload.get("usage") or {}
        choices = payload.get("choices") or []
        first_choice = choices[0] if choices else {}
        message = first_choice.get("message") or {}
        content = message.get("content") or ""
        generation_id = payload.get("id") or ""
        cost = usage.get("cost")
        if cost is None and generation_id:
            stats = self.generation_stats(generation_id)
            cost = _extract_generation_cost(stats)
        return OpenRouterResponse(
            generation_id=generation_id,
            model=payload.get("model") or config.model,
            content=content,
            finish_reason=first_choice.get("finish_reason"),
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            total_tokens=int(usage.get("total_tokens") or 0),
            cost_usd=float(cost or 0.0),
            raw=payload,
        )

    def generation_stats(self, generation_id: str) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/generation",
            headers=self._headers(),
            params={"id": generation_id},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return _json_payload(response, context="OpenRouter generation stats")


def _extract_generation_cost(payload: dict[str, Any]) -> float | None:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    for key in ("total_cost", "cost"):
        if key in data and data[key] is not None:
            return float(data[key])
    return None


def _json_payload(response: Any, *, context: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise OpenRouterResponseError(
            f"{context} returned non-JSON response "
            f"(status={getattr(response, 'status_code', 'unknown')}, "
            f"content_type={_response_content_type(response)!r}, "
            f"body_preview={_response_text_preview(response)!r})"
        ) from exc
    if not isinstance(payload, dict):
        raise OpenRouterResponseError(
            f"{context} returned JSON {type(payload).__name__}, expected object "
            f"(status={getattr(response, 'status_code', 'unknown')})"
        )
    return payload


def _response_content_type(response: Any) -> str | None:
    headers = getattr(response, "headers", {}) or {}
    try:
        return headers.get("content-type") or headers.get("Content-Type")
    except AttributeError:
        return None


def _response_text_preview(response: Any, limit: int = 500) -> str:
    text = getattr(response, "text", "") or ""
    normalized = " ".join(str(text).split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}…"
