"""HTTP transport for the EVALSURE REST API."""

from __future__ import annotations

from typing import Any

import httpx

from evalsure_sdk.exceptions import (
    EvalSureAPIError,
    EvalSureAuthenticationError,
    EvalSureNotFoundError,
    EvalSureTimeoutError,
    EvalSureValidationError,
    _redact,
)


class HttpTransport:
    """Thin httpx wrapper. Credentials live only in headers, never in logs."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        access_token: str | None = None,
        timeout: float = 30.0,
        api_prefix: str = "/api/v1",
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required")
        self.base_url = base_url.rstrip("/")
        self.api_prefix = api_prefix.rstrip("/") or "/api/v1"
        self.api_key = api_key
        self.access_token = access_token
        self.timeout = timeout
        self._secrets = [s for s in (api_key, access_token) if s]

    def _headers(self, *, require_jwt: bool = False) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if require_jwt:
            if not self.access_token:
                raise EvalSureAuthenticationError(
                    "This endpoint requires a JWT access token "
                    "(EVALSURE_ACCESS_TOKEN / client access_token). "
                    "API keys cannot create or list projects.",
                    status_code=401,
                )
            headers["Authorization"] = f"Bearer {self.access_token}"
            return headers

        # Prefer API key when present (matches backend get_auth_context).
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        elif self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        else:
            raise EvalSureAuthenticationError(
                "No credentials configured. Set api_key or access_token.",
                status_code=401,
            )
        return headers

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{self.api_prefix}{path}"

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        require_jwt: bool = False,
        expect_json: bool = True,
    ) -> Any:
        url = self._url(path)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(
                    method,
                    url,
                    headers=self._headers(require_jwt=require_jwt),
                    json=json,
                )
        except httpx.TimeoutException as exc:
            raise EvalSureTimeoutError("Request timed out") from exc
        except httpx.ConnectError as exc:
            raise EvalSureTimeoutError("Could not connect to EVALSURE API") from exc
        except httpx.HTTPError as exc:
            raise EvalSureTimeoutError(f"HTTP transport error: {exc}") from exc

        return self._handle_response(response, expect_json=expect_json)

    def _handle_response(self, response: httpx.Response, *, expect_json: bool) -> Any:
        if response.status_code == 204:
            return None

        detail: Any = None
        message = response.reason_phrase or "API request failed"
        if response.content:
            try:
                payload = response.json()
                if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
                    err = payload["error"]
                    detail = err
                    if isinstance(err.get("message"), str):
                        message = err["message"]
                else:
                    detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
                    if isinstance(detail, str):
                        message = detail
                    elif isinstance(detail, list):
                        message = "; ".join(
                            str(item.get("msg", item)) if isinstance(item, dict) else str(item)
                            for item in detail
                        )
                    elif isinstance(detail, dict) and "message" in detail:
                        message = str(detail["message"])
                    elif detail is not None:
                        message = str(detail)
            except ValueError:
                message = response.text[:500] or message

        message = _redact(message, self._secrets)

        if response.status_code in {401, 403}:
            raise EvalSureAuthenticationError(message, status_code=response.status_code, detail=detail)
        if response.status_code == 404:
            raise EvalSureNotFoundError(message, status_code=404, detail=detail)
        if response.status_code in {400, 409, 422}:
            raise EvalSureValidationError(message, status_code=response.status_code, detail=detail)
        if response.status_code >= 400:
            raise EvalSureAPIError(message, status_code=response.status_code, detail=detail)

        if not expect_json:
            return response.content
        if not response.content:
            return None
        return response.json()
