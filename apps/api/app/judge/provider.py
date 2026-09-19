"""LLM judge provider abstraction and concrete implementations."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import httpx

from app.core.config import get_settings
from app.judge.errors import JudgeEvaluationError
from app.judge.prompt import JUDGE_SYSTEM_INSTRUCTION


@dataclass
class JudgeCompletion:
    """Provider-agnostic judge response with optional latency / token usage."""

    content: str
    provider: str
    model: str | None = None
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def to_model_call_data(self) -> dict:
        """Structured model_call metadata — never includes secrets."""
        data: dict = {"provider": self.provider}
        if self.model is not None:
            data["model"] = self.model
        if self.latency_ms is not None:
            data["latency_ms"] = self.latency_ms
        if self.input_tokens is not None:
            data["input_tokens"] = self.input_tokens
        if self.output_tokens is not None:
            data["output_tokens"] = self.output_tokens
        if self.total_tokens is not None:
            data["total_tokens"] = self.total_tokens
        return data


@runtime_checkable
class LLMJudgeProvider(Protocol):
    """Pluggable judge backend — OpenAI, Anthropic, Gemini, Ollama, etc. later."""

    name: str

    def complete(self, prompt: str) -> JudgeCompletion:
        """Send the judge prompt and return content + optional usage metadata."""
        ...


def _parse_usage(payload: dict) -> tuple[int | None, int | None, int | None]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None, None, None
    input_tokens = usage.get("prompt_tokens")
    output_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    try:
        in_t = int(input_tokens) if input_tokens is not None else None
    except (TypeError, ValueError):
        in_t = None
    try:
        out_t = int(output_tokens) if output_tokens is not None else None
    except (TypeError, ValueError):
        out_t = None
    try:
        total_t = int(total_tokens) if total_tokens is not None else None
    except (TypeError, ValueError):
        total_t = None
    return in_t, out_t, total_t


class OpenAICompatibleJudgeProvider:
    """HTTP chat-completions client (OpenAI and compatible base URLs)."""

    name = "openai_compatible"

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def complete(self, prompt: str) -> JudgeCompletion:
        if not self.api_key:
            raise JudgeEvaluationError(
                "EVALSURE_JUDGE_API_KEY is not configured; cannot call llm_judge provider"
            )

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": JUDGE_SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt},
            ],
        }
        started = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, headers=headers, json=body)
        except httpx.TimeoutException as exc:
            raise JudgeEvaluationError("Judge provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise JudgeEvaluationError(f"Judge provider unavailable: {exc}") from exc

        latency_ms = (time.perf_counter() - started) * 1000.0

        if response.status_code >= 400:
            raise JudgeEvaluationError(
                f"Judge provider HTTP {response.status_code}: request failed"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise JudgeEvaluationError("Judge provider returned non-JSON body") from exc

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise JudgeEvaluationError("Judge provider response missing message content") from exc

        if not isinstance(content, str):
            raise JudgeEvaluationError("Judge provider content is not a string")

        input_tokens, output_tokens, total_tokens = _parse_usage(payload)
        return JudgeCompletion(
            content=content,
            provider=self.name,
            model=self.model,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )


class FakeLLMJudgeProvider:
    """Deterministic provider for tests — never hits the network."""

    name = "fake"

    def __init__(
        self,
        response: str | JudgeCompletion | Exception | None = None,
        *,
        latency_ms: float | None = 12.0,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        model: str = "fake-model",
    ) -> None:
        self._response: str | JudgeCompletion | Exception = (
            '{"score": 0.91, "reason": "Aligned with the reference."}'
            if response is None
            else response
        )
        self.latency_ms = latency_ms
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens
        self.model = model
        self.calls: list[str] = []

    def complete(self, prompt: str) -> JudgeCompletion:
        self.calls.append(prompt)
        if isinstance(self._response, Exception):
            raise self._response
        if isinstance(self._response, JudgeCompletion):
            return self._response
        return JudgeCompletion(
            content=self._response,
            provider=self.name,
            model=self.model,
            latency_ms=self.latency_ms,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            total_tokens=self.total_tokens,
        )


_provider_override: LLMJudgeProvider | None = None


def set_judge_provider_override(provider: LLMJudgeProvider | None) -> None:
    global _provider_override
    _provider_override = provider


def clear_judge_provider_override() -> None:
    set_judge_provider_override(None)


def get_judge_provider() -> LLMJudgeProvider:
    if _provider_override is not None:
        return _provider_override

    settings = get_settings()
    provider_name = (settings.judge_provider or "openai_compatible").strip().lower()
    if provider_name in {"openai_compatible", "openai"}:
        return OpenAICompatibleJudgeProvider(
            api_key=settings.judge_api_key,
            model=settings.judge_model,
            base_url=settings.judge_base_url,
            timeout_seconds=settings.judge_timeout_seconds,
        )
    raise JudgeEvaluationError(
        f"Unsupported EVALSURE_JUDGE_PROVIDER '{provider_name}'. "
        "Supported: openai_compatible"
    )


def judge_config_for_snapshot() -> dict[str, str]:
    """Non-secret judge settings for immutable config_snapshot."""
    settings = get_settings()
    return {
        "provider": (settings.judge_provider or "openai_compatible").strip().lower(),
        "model": settings.judge_model,
        "base_url": settings.judge_base_url,
    }
