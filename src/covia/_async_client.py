"""Asynchronous HTTP client for the Covia REST API."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
from httpx_sse import aconnect_sse

from covia._sse import SSEEvent
from covia._transport import TransportConfig
from covia.exceptions import (
    AssetNotFoundError,
    CoviaConnectionError,
    CoviaTimeoutError,
    GridError,
    JobNotFoundError,
)
from covia.models import (
    AgentCard,
    AssetList,
    DIDDocument,
    JobData,
    MCPDiscovery,
    OperationInfo,
    VenueStatus,
)

logger = logging.getLogger(__name__)


class AsyncCoviaHTTPClient:
    """Low-level async HTTP client wrapping ``httpx.AsyncClient``.

    Async mirror of :class:`~covia._client.CoviaHTTPClient`.
    """

    def __init__(self, config: TransportConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.api_url,
            timeout=config.timeout,
            headers=config.headers,
            follow_redirects=config.follow_redirects,
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._client.aclose()

    async def __aenter__(self) -> AsyncCoviaHTTPClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def get_status(self) -> VenueStatus:
        """``GET /api/v1/status``"""
        resp = await self._request("GET", "status")
        return VenueStatus.model_validate(resp.json())

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    async def list_assets(self, offset: int = 0, limit: int | None = None) -> AssetList:
        """``GET /api/v1/assets``"""
        params: dict[str, Any] = {"offset": offset}
        if limit is not None:
            params["limit"] = limit
        resp = await self._request("GET", "assets", params=params)
        return AssetList.model_validate(resp.json())

    async def register_asset(self, metadata: dict[str, Any]) -> str:
        """``POST /api/v1/assets`` — returns the new asset ID."""
        resp = await self._request("POST", "assets", json=metadata)
        return resp.text.strip().strip('"')

    async def get_asset_metadata(self, asset_id: str) -> tuple[dict[str, Any], str]:
        """``GET /api/v1/assets/{id}``

        Returns:
            A tuple of (parsed metadata dict, raw UTF-8 response text).
            The raw text is preserved for asset ID computation/validation
            (asset IDs are the SHA-256 hash of canonical metadata bytes).
        """
        resp = await self._request_asset("GET", f"assets/{asset_id}", asset_id)
        result: dict[str, Any] = resp.json()
        return result, resp.text

    async def get_asset_content(self, asset_id: str) -> bytes:
        """``GET /api/v1/assets/{id}/content``"""
        resp = await self._request_asset("GET", f"assets/{asset_id}/content", asset_id)
        return resp.content

    async def put_asset_content(self, asset_id: str, content: bytes) -> str:
        """``PUT /api/v1/assets/{id}/content`` — returns the content hash."""
        resp = await self._request_asset("PUT", f"assets/{asset_id}/content", asset_id, content=content)
        return resp.text.strip().strip('"')

    # ------------------------------------------------------------------
    # Jobs / Invoke
    # ------------------------------------------------------------------

    async def invoke(self, operation: str, input: Any = None, *, ucans: list[str] | None = None) -> JobData:
        """``POST /api/v1/invoke``.

        ``ucans`` is an optional list of UCAN proof tokens authorising
        capability-gated operations.
        """
        body: dict[str, Any] = {"operation": operation}
        if input is not None:
            body["input"] = input
        if ucans:
            body["ucans"] = list(ucans)
        resp = await self._request("POST", "invoke", json=body)
        return JobData.model_validate(resp.json())

    async def get_job(self, job_id: str) -> JobData:
        """``GET /api/v1/jobs/{id}``"""
        resp = await self._request_job("GET", f"jobs/{job_id}", job_id)
        return JobData.model_validate(resp.json())

    async def list_jobs(self) -> list[str]:
        """``GET /api/v1/jobs``"""
        resp = await self._request("GET", "jobs")
        result: list[str] = resp.json()
        return result

    async def cancel_job(self, job_id: str) -> JobData:
        """``PUT /api/v1/jobs/{id}/cancel``"""
        resp = await self._request_job("PUT", f"jobs/{job_id}/cancel", job_id)
        return JobData.model_validate(resp.json())

    async def delete_job(self, job_id: str) -> None:
        """``PUT /api/v1/jobs/{id}/delete``"""
        await self._request_job("PUT", f"jobs/{job_id}/delete", job_id)

    async def stream_job_events(self, job_id: str) -> AsyncIterator[SSEEvent]:
        """``GET /api/v1/jobs/{id}/sse`` — yields SSE events."""
        async with aconnect_sse(self._client, "GET", f"jobs/{job_id}/sse") as event_source:
            async for sse in event_source.aiter_sse():
                yield SSEEvent(
                    event=sse.event if sse.event else None,
                    data=sse.data,
                    id=sse.id if sse.id else None,
                    retry=sse.retry,
                )

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    async def list_operations(self) -> list[OperationInfo]:
        """``GET /api/v1/operations``"""
        resp = await self._request("GET", "operations")
        return [OperationInfo.model_validate(item) for item in resp.json()]

    async def get_operation(self, name: str) -> OperationInfo:
        """``GET /api/v1/operations/{name}``"""
        resp = await self._request("GET", f"operations/{name}")
        return OperationInfo.model_validate(resp.json())

    # ------------------------------------------------------------------
    # Secrets
    # ------------------------------------------------------------------

    async def list_secrets(self) -> list[str]:
        """``GET /api/v1/secrets`` — returns the list of secret names."""
        resp = await self._request("GET", "secrets")
        body: dict[str, Any] = resp.json()
        items: list[str] = body.get("items", [])
        return items

    async def put_secret(self, name: str, value: str) -> None:
        """``PUT /api/v1/secrets/{name}`` — store a secret value."""
        await self._request("PUT", f"secrets/{name}", json={"value": value})

    async def delete_secret(self, name: str) -> None:
        """``DELETE /api/v1/secrets/{name}`` — delete a secret."""
        await self._request("DELETE", f"secrets/{name}")

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    async def get_did_document(self) -> DIDDocument:
        """``GET /.well-known/did.json``"""
        base = self._config.base_url.rstrip("/")
        resp = await self._raw_request("GET", f"{base}/.well-known/did.json")
        return DIDDocument.model_validate(resp.json())

    async def get_asset_did_document(self, asset_id: str) -> DIDDocument:
        """``GET /a/{id}/did.json``"""
        base = self._config.base_url.rstrip("/")
        resp = await self._raw_request("GET", f"{base}/a/{asset_id}/did.json")
        return DIDDocument.model_validate(resp.json())

    async def get_mcp_discovery(self) -> MCPDiscovery:
        """``GET /.well-known/mcp``"""
        base = self._config.base_url.rstrip("/")
        resp = await self._raw_request("GET", f"{base}/.well-known/mcp")
        return MCPDiscovery.model_validate(resp.json())

    async def get_agent_card(self) -> AgentCard:
        """``GET /.well-known/agent-card.json``"""
        base = self._config.base_url.rstrip("/")
        resp = await self._raw_request("GET", f"{base}/.well-known/agent-card.json")
        return AgentCard.model_validate(resp.json())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _request_asset(self, method: str, path: str, asset_id: str, **kwargs: Any) -> httpx.Response:
        """Like ``_request`` but raises :class:`AssetNotFoundError` on 404."""
        try:
            return await self._request(method, path, **kwargs)
        except GridError as exc:
            if exc.status_code == 404:
                raise AssetNotFoundError(asset_id) from exc
            raise

    async def _request_job(self, method: str, path: str, job_id: str, **kwargs: Any) -> httpx.Response:
        """Like ``_request`` but raises :class:`JobNotFoundError` on 404."""
        try:
            return await self._request(method, path, **kwargs)
        except GridError as exc:
            if exc.status_code == 404:
                raise JobNotFoundError(job_id) from exc
            raise

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Make an API request (relative to the /api/v1/ base)."""
        self._apply_auth(kwargs)
        logger.debug("%s %s", method, path)
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.ConnectError as exc:
            logger.debug("Connection failed: %s %s — %s", method, path, exc)
            raise CoviaConnectionError(str(exc)) from exc
        except httpx.TimeoutException as exc:
            logger.debug("Request timed out: %s %s — %s", method, path, exc)
            raise CoviaTimeoutError(str(exc)) from exc
        logger.debug("%s %s → %d", method, path, response.status_code)
        self._handle_error(response)
        return response

    async def _raw_request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Make a request to an absolute URL (for discovery endpoints)."""
        self._apply_auth(kwargs)
        logger.debug("%s %s", method, url)
        try:
            response = await self._client.request(method, url, **kwargs)
        except httpx.ConnectError as exc:
            logger.debug("Connection failed: %s %s — %s", method, url, exc)
            raise CoviaConnectionError(str(exc)) from exc
        except httpx.TimeoutException as exc:
            logger.debug("Request timed out: %s %s — %s", method, url, exc)
            raise CoviaTimeoutError(str(exc)) from exc
        logger.debug("%s %s → %d", method, url, response.status_code)
        self._handle_error(response)
        return response

    def _apply_auth(self, kwargs: dict[str, Any]) -> None:
        """Inject authentication headers into request kwargs."""
        if self._config.auth is not None:
            auth_headers: dict[str, str] = {}
            self._config.auth.apply(auth_headers)
            if auth_headers:
                headers = dict(kwargs.get("headers", {}))
                headers.update(auth_headers)
                kwargs["headers"] = headers

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
        raise GridError(
            status_code=response.status_code,
            message=message,
            response_body=body,
        )
