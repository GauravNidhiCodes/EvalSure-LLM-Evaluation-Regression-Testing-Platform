"""EVALSURE CLI configuration from environment / options."""

from __future__ import annotations

import os
from dataclasses import dataclass

from evalsure_sdk import EvalSureClient

DEFAULT_API_URL = "http://localhost:8000"


@dataclass
class CliConfig:
    api_url: str
    api_key: str | None
    access_token: str | None
    timeout: float = 30.0

    def client(self) -> EvalSureClient:
        return EvalSureClient(
            base_url=self.api_url,
            api_key=self.api_key,
            access_token=self.access_token,
            timeout=self.timeout,
        )


def load_config(
    *,
    api_url: str | None = None,
    api_key: str | None = None,
    access_token: str | None = None,
    timeout: float | None = None,
) -> CliConfig:
    return CliConfig(
        api_url=(api_url or os.environ.get("EVALSURE_API_URL") or DEFAULT_API_URL).rstrip("/"),
        api_key=api_key or os.environ.get("EVALSURE_API_KEY"),
        access_token=access_token or os.environ.get("EVALSURE_ACCESS_TOKEN"),
        timeout=float(timeout if timeout is not None else os.environ.get("EVALSURE_TIMEOUT", "30")),
    )
