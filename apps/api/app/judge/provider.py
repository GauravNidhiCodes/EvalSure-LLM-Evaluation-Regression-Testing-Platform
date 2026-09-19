"""LLM judge provider abstraction and concrete implementations."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import httpx

from app.core.config import get_settings
from app.judge.errors import JudgeEvaluationError
from app.judge.prompt import JUDGE_SYSTEM_INSTRUCTION


@runtime_checkable
class LLMJudgeProvider(Protocol):
    """Pluggable judge backend — OpenAI, Anthropic, Gemini, Ollama, etc. later."""

    name: str

    def complete(self, prompt: str) -> str:
        """Send the judge prompt and return the raw model response text."""
        ...


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

    def complete(self, prompt: str) -> str:
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
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, headers=headers, json=body)
        except httpx.TimeoutException as exc:
            raise JudgeEvaluationError("Judge provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise JudgeEvaluationError(f"Judge provider unavailable: {exc}") from exc

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
        return content


class FakeLLMJudgeProvider:
    """Deterministic provider for tests — never hits the network."""

    name = "fake"

    def __init__(self, response: str | Exception | None = None) -> None:
        self._response: str | Exception = (
            '{"score": 0.91, "reason": "Aligned with the reference."}'
            if response is None
            else response
        )
        self.calls: list[str] = []

    def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


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
