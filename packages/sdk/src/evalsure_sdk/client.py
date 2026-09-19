"""EvalSureClient — typed client for the EVALSURE REST API."""

from __future__ import annotations

from evalsure_sdk._http import HttpTransport
from evalsure_sdk.resources import (
    DatasetsAPI,
    ExperimentsAPI,
    ProjectsAPI,
    RunsAPI,
    TracesAPI,
)

DEFAULT_TIMEOUT_SECONDS = 30.0


class EvalSureClient:
    """HTTP client for EVALSURE.

    Authentication:
      - ``api_key`` → ``X-API-Key`` header (project-scoped operations)
      - ``access_token`` → ``Authorization: Bearer`` (required for project
        create/list; optional otherwise)

    Credentials are never logged or persisted by the SDK.
    """

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        access_token: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        api_prefix: str = "/api/v1",
    ) -> None:
        self._transport = HttpTransport(
            base_url=base_url,
            api_key=api_key,
            access_token=access_token,
            timeout=timeout,
            api_prefix=api_prefix,
        )
        self.projects = ProjectsAPI(self._transport)
        self.datasets = DatasetsAPI(self._transport)
        self.runs = RunsAPI(self._transport)
        self.experiments = ExperimentsAPI(self._transport)
        self.traces = TracesAPI(self._transport)

    @property
    def base_url(self) -> str:
        return self._transport.base_url

    @property
    def timeout(self) -> float:
        return self._transport.timeout

    def __repr__(self) -> str:
        auth = "api_key" if self._transport.api_key else ("jwt" if self._transport.access_token else "none")
        return f"EvalSureClient(base_url={self.base_url!r}, auth={auth!r}, timeout={self.timeout})"
