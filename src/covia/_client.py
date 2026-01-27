"""Synchronous HTTP client for the Covia REST API."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx
from httpx_sse import connect_sse

from covia._sse import SSEEvent
from covia._transport import TransportConfig
from covia.exceptions import CoviaAPIError, CoviaConnectionError, CoviaTimeoutError
from covia.models import (
    AgentCard,
    AssetList,
    DIDDocument,
    JobData,
    MCPDiscovery,
    VenueStatus,
)


class CoviaHTTPClient:
    """Low-level synchronous HTTP client wrapping ``httpx.Client``.

    Each public method maps 1:1 to a Covia REST API endpoint.
    """

    def __init__(self, config: TransportConfig) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.api_url,
            timeout=config.timeout,
            headers=config.headers,
            follow_redirects=config.follow_redirects,
        )

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> CoviaHTTPClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> VenueStatus:
        """``GET /api/v1/status``"""
        resp = self._request("GET", "status")
        return VenueStatus.model_validate(resp.json())

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    def list_assets(self, offset: int = 0, limit: int | None = None) -> AssetList:
        """``GET /api/v1/assets``"""
        params: dict[str, Any] = {"offset": offset}
        if limit is not None:
            params["limit"] = limit
        resp = self._request("GET", "assets", params=params)
        return AssetList.model_validate(resp.json())

    def register_asset(self, metadata: dict[str, Any]) -> str:
        """``POST /api/v1/assets`` — returns the new asset ID."""
        resp = self._request("POST", "assets", json=metadata)
        return resp.text.strip().strip('"')

    def get_asset_metadata(self, asset_id: str) -> dict[str, Any]:
        """``GET /api/v1/assets/{id}``"""
        resp = self._request("GET", f"assets/{asset_id}")
        result: dict[str, Any] = resp.json()
        return result

    def get_asset_content(self, asset_id: str) -> bytes:
        """``GET /api/v1/assets/{id}/content``"""
        resp = self._request("GET", f"assets/{asset_id}/content")
        return resp.content

    def put_asset_content(self, asset_id: str, content: bytes) -> str:
        """``PUT /api/v1/assets/{id}/content`` — returns the content hash."""
        resp = self._request("PUT", f"assets/{asset_id}/content", content=content)
        return resp.text.strip().strip('"')

    # ------------------------------------------------------------------
    # Jobs / Invoke
    # ------------------------------------------------------------------

    def invoke(self, operation: str, input: Any = None) -> JobData:
        """``POST /api/v1/invoke``"""
        body: dict[str, Any] = {"operation": operation}
        if input is not None:
            body["input"] = input
        resp = self._request("POST", "invoke", json=body)
        return JobData.model_validate(resp.json())

    def get_job(self, job_id: str) -> JobData:
        """``GET /api/v1/jobs/{id}``"""
        resp = self._request("GET", f"jobs/{job_id}")
        return JobData.model_validate(resp.json())

    def list_jobs(self) -> list[str]:
        """``GET /api/v1/jobs``"""
        resp = self._request("GET", "jobs")
        result: list[str] = resp.json()
        return result

    def cancel_job(self, job_id: str) -> JobData:
        """``PUT /api/v1/jobs/{id}/cancel``"""
        resp = self._request("PUT", f"jobs/{job_id}/cancel")
        return JobData.model_validate(resp.json())

    def delete_job(self, job_id: str) -> None:
        """``PUT /api/v1/jobs/{id}/delete``"""
        self._request("PUT", f"jobs/{job_id}/delete")

    def stream_job_events(self, job_id: str) -> Iterator[SSEEvent]:
        """``GET /api/v1/jobs/{id}/sse`` — yields SSE events."""
        with connect_sse(
            self._client, "GET", f"jobs/{job_id}/sse"
        ) as event_source:
            for sse in event_source.iter_sse():
                yield SSEEvent(
                    event=sse.event if sse.event else None,
                    data=sse.data,
                    id=sse.id if sse.id else None,
                    retry=sse.retry,
                )

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def get_did_document(self) -> DIDDocument:
        """``GET /.well-known/did.json``"""
        base = self._config.base_url.rstrip("/")
        resp = self._raw_request("GET", f"{base}/.well-known/did.json")
        return DIDDocument.model_validate(resp.json())

    def get_asset_did_document(self, asset_id: str) -> DIDDocument:
        """``GET /a/{id}/did.json``"""
        base = self._config.base_url.rstrip("/")
        resp = self._raw_request("GET", f"{base}/a/{asset_id}/did.json")
        return DIDDocument.model_validate(resp.json())

    def get_mcp_discovery(self) -> MCPDiscovery:
        """``GET /.well-known/mcp``"""
        base = self._config.base_url.rstrip("/")
        resp = self._raw_request("GET", f"{base}/.well-known/mcp")
        return MCPDiscovery.model_validate(resp.json())

    def get_agent_card(self) -> AgentCard:
        """``GET /.well-known/agent-card.json``"""
        base = self._config.base_url.rstrip("/")
        resp = self._raw_request("GET", f"{base}/.well-known/agent-card.json")
        return AgentCard.model_validate(resp.json())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Make an API request (relative to the /api/v1/ base)."""
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.ConnectError as exc:
            raise CoviaConnectionError(str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise CoviaTimeoutError(str(exc)) from exc
        self._handle_error(response)
        return response

    def _raw_request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Make a request to an absolute URL (for discovery endpoints)."""
        try:
            response = self._client.request(method, url, **kwargs)
        except httpx.ConnectError as exc:
            raise CoviaConnectionError(str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise CoviaTimeoutError(str(exc)) from exc
        self._handle_error(response)
        return response

    def _handle_error(self, response: httpx.Response) -> None:
        """Raise an appropriate exception for error responses."""
        if response.status_code < 400:
            return
        try:
            body = response.json()
            message = body.get("error", response.text) if isinstance(body, dict) else response.text
        except Exception:
            body = None
            message = response.text
        raise CoviaAPIError(
            status_code=response.status_code,
            message=message,
            response_body=body,
        )
