"""Synchronous HTTP client for the Covia REST API."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

import httpx
from httpx_sse import connect_sse

from covia._retry import BUDGET_MS, parse_retry_after_ms, retry_delay_ms
from covia._sse import SSEEvent
from covia._transport import TransportConfig
from covia.exceptions import (
    AssetNotFoundError,
    CoviaConnectionError,
    CoviaTimeoutError,
    GridError,
    JobNotFoundError,
    RateLimitError,
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


class CoviaHTTPClient:
    """Low-level synchronous HTTP client wrapping ``httpx.Client``.

    Each public method maps 1:1 to a Covia REST API endpoint.
    """

    def __init__(self, config: TransportConfig) -> None:
        self._config = config
        # Cached venue DID for audience-bound auth (resolved from did.json on
        # first use). ``_resolving_did`` guards the bootstrap fetch so it does
        # not recurse through auth resolution.
        self._venue_did: str | None = None
        self._resolving_did: bool = False
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

    def get_asset_metadata(self, asset_id: str) -> tuple[dict[str, Any], str]:
        """``GET /api/v1/assets/{id}``

        Returns:
            A tuple of (parsed metadata dict, raw UTF-8 response text).
            The raw text is preserved for asset ID computation/validation
            (asset IDs are the SHA-256 hash of canonical metadata bytes).
        """
        resp = self._request_asset("GET", f"assets/{asset_id}", asset_id)
        result: dict[str, Any] = resp.json()
        return result, resp.text

    def get_asset_content(self, asset_id: str) -> bytes:
        """``GET /api/v1/assets/{id}/content``"""
        resp = self._request_asset("GET", f"assets/{asset_id}/content", asset_id)
        return resp.content

    def put_asset_content(self, asset_id: str, content: bytes) -> str:
        """``PUT /api/v1/assets/{id}/content`` — returns the content hash."""
        resp = self._request_asset("PUT", f"assets/{asset_id}/content", asset_id, content=content)
        return resp.text.strip().strip('"')

    # ------------------------------------------------------------------
    # Jobs / Invoke
    # ------------------------------------------------------------------

    def invoke(
        self,
        operation: str,
        input: Any = None,
        *,
        ucans: list[str] | None = None,
        private: bool = False,
        wait: bool | int | None = None,
    ) -> JobData:
        """``POST /api/v1/invoke``.

        ``ucans`` is an optional list of UCAN proof tokens authorising
        capability-gated operations (e.g. cross-DID reads). ``private`` runs a
        memory-only job (covia #192); ``wait`` blocks server-side (``True`` =
        the venue's wait cap, an int = milliseconds) and returns the finished
        record when the job completes within the window.
        """
        body: dict[str, Any] = {"operation": operation}
        if input is not None:
            body["input"] = input
        if ucans:
            body["ucans"] = list(ucans)
        if private:
            body["private"] = True
        if wait is not None:
            body["wait"] = wait
        resp = self._request("POST", "invoke", json=body)
        return JobData.model_validate(resp.json())

    def get_job(self, job_id: str) -> JobData:
        """``GET /api/v1/jobs/{id}``"""
        resp = self._request_job("GET", f"jobs/{job_id}", job_id)
        return JobData.model_validate(resp.json())

    def list_jobs(self) -> list[str]:
        """``GET /api/v1/jobs``"""
        resp = self._request("GET", "jobs")
        result: list[str] = resp.json()
        return result

    def cancel_job(self, job_id: str) -> JobData:
        """``PUT /api/v1/jobs/{id}/cancel``"""
        resp = self._request_job("PUT", f"jobs/{job_id}/cancel", job_id)
        return JobData.model_validate(resp.json())

    def delete_job(self, job_id: str) -> None:
        """``PUT /api/v1/jobs/{id}/delete``"""
        self._request_job("PUT", f"jobs/{job_id}/delete", job_id)

    def pause_job(self, job_id: str) -> JobData:
        """``PUT /api/v1/jobs/{id}/pause``"""
        resp = self._request_job("PUT", f"jobs/{job_id}/pause", job_id)
        return JobData.model_validate(resp.json())

    def resume_job(self, job_id: str) -> JobData:
        """``PUT /api/v1/jobs/{id}/resume``"""
        resp = self._request_job("PUT", f"jobs/{job_id}/resume", job_id)
        return JobData.model_validate(resp.json())

    def send_job_message(self, job_id: str, message: Any) -> dict[str, Any]:
        """``POST /api/v1/jobs/{id}`` — deliver a message to a running job.

        Returns the venue's queue acknowledgement (``{status, queueDepth}``).
        A non-object *message* is wrapped by the venue as ``{content: message}``.
        """
        resp = self._request_job("POST", f"jobs/{job_id}", job_id, json=message)
        result: dict[str, Any] = resp.json()
        return result

    def stream_job_events(self, job_id: str) -> Iterator[SSEEvent]:
        """``GET /api/v1/jobs/{id}/sse`` — yields SSE events."""
        with connect_sse(self._client, "GET", f"jobs/{job_id}/sse") as event_source:
            for sse in event_source.iter_sse():
                yield SSEEvent(
                    event=sse.event if sse.event else None,
                    data=sse.data,
                    id=sse.id if sse.id else None,
                    retry=sse.retry,
                )

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def list_operations(self) -> list[OperationInfo]:
        """``GET /api/v1/operations``"""
        resp = self._request("GET", "operations")
        return [OperationInfo.model_validate(item) for item in resp.json()]

    def get_operation(self, name: str) -> OperationInfo:
        """``GET /api/v1/operations/{name}``"""
        resp = self._request("GET", f"operations/{name}")
        return OperationInfo.model_validate(resp.json())

    # ------------------------------------------------------------------
    # Values — job-free lattice reads (covia #177)
    # ------------------------------------------------------------------

    def get_agents(self, suffix: str, params: dict[str, Any]) -> dict[str, Any]:
        """``GET /api/v1/agents{suffix}`` — the job-free agent read transport
        (covia #180) behind ``agents.list``/``agents.info``. Creates no Job."""
        clean = {k: v for k, v in params.items() if v is not None}
        resp = self._request("GET", f"agents{suffix}", params=clean)
        result: dict[str, Any] = resp.json()
        return result

    def get_value(self, op: str, params: dict[str, Any]) -> dict[str, Any]:
        """``GET /api/v1/values/{op}`` — a synchronous, capability-checked lattice
        read that creates **no Job** (unlike the invoke path). ``None`` params are
        dropped from the query string."""
        clean = {k: v for k, v in params.items() if v is not None}
        resp = self._request("GET", f"values/{op}", params=clean)
        result: dict[str, Any] = resp.json()
        return result

    # ------------------------------------------------------------------
    # Secrets
    # ------------------------------------------------------------------

    def list_secrets(self) -> list[str]:
        """``GET /api/v1/secrets`` — returns the list of secret names."""
        resp = self._request("GET", "secrets")
        body: dict[str, Any] = resp.json()
        items: list[str] = body.get("items", [])
        return items

    def delete_secret(self, name: str) -> None:
        """``DELETE /api/v1/secrets/{name}`` — delete a secret."""
        self._request("DELETE", f"secrets/{name}")

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def get_did_document(self) -> DIDDocument:
        """``GET /.well-known/did.json``"""
        base = self._config.base_url.rstrip("/")
        resp = self._raw_request("GET", f"{base}/.well-known/did.json")
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

    def _request_asset(self, method: str, path: str, asset_id: str, **kwargs: Any) -> httpx.Response:
        """Like ``_request`` but raises :class:`AssetNotFoundError` on 404."""
        try:
            return self._request(method, path, **kwargs)
        except GridError as exc:
            if exc.status_code == 404:
                raise AssetNotFoundError(asset_id) from exc
            raise

    def _request_job(self, method: str, path: str, job_id: str, **kwargs: Any) -> httpx.Response:
        """Like ``_request`` but raises :class:`JobNotFoundError` on 404."""
        try:
            return self._request(method, path, **kwargs)
        except GridError as exc:
            if exc.status_code == 404:
                raise JobNotFoundError(job_id) from exc
            raise

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Make an API request (relative to the /api/v1/ base)."""
        self._apply_auth(kwargs)
        import random as _random
        import time as _time

        deadline_ms = _time.monotonic() * 1000 + BUDGET_MS
        attempt = 0
        while True:
            attempt += 1
            logger.debug("%s %s", method, path)
            try:
                response = self._client.request(method, path, **kwargs)
            except httpx.ConnectError as exc:
                logger.debug("Connection failed: %s %s — %s", method, path, exc)
                raise CoviaConnectionError(str(exc)) from exc
            except httpx.TimeoutException as exc:
                logger.debug("Request timed out: %s %s — %s", method, path, exc)
                raise CoviaTimeoutError(str(exc)) from exc
            logger.debug("%s %s → %d", method, path, response.status_code)
            # 429 backpressure: refused before any effect — retry per policy.
            if response.status_code == 429:
                now_ms = _time.monotonic() * 1000
                retry_after_ms = parse_retry_after_ms(response.headers.get("Retry-After"), _time.time() * 1000)
                delay_ms = retry_delay_ms(attempt, retry_after_ms, deadline_ms - now_ms, _random.random())
                if delay_ms >= 0:
                    logger.debug("429 from %s; retrying in %dms (attempt %d)", path, delay_ms, attempt)
                    time.sleep(delay_ms / 1000)
                    continue
            self._handle_error(response)
            return response

    def _raw_request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Make a request to an absolute URL (for discovery endpoints)."""
        self._apply_auth(kwargs)
        import random as _random
        import time as _time

        deadline_ms = _time.monotonic() * 1000 + BUDGET_MS
        attempt = 0
        while True:
            attempt += 1
            logger.debug("%s %s", method, url)
            try:
                response = self._client.request(method, url, **kwargs)
            except httpx.ConnectError as exc:
                logger.debug("Connection failed: %s %s — %s", method, url, exc)
                raise CoviaConnectionError(str(exc)) from exc
            except httpx.TimeoutException as exc:
                logger.debug("Request timed out: %s %s — %s", method, url, exc)
                raise CoviaTimeoutError(str(exc)) from exc
            logger.debug("%s %s → %d", method, url, response.status_code)
            # 429 backpressure: refused before any effect — retry per policy.
            if response.status_code == 429:
                now_ms = _time.monotonic() * 1000
                retry_after_ms = parse_retry_after_ms(response.headers.get("Retry-After"), _time.time() * 1000)
                delay_ms = retry_delay_ms(attempt, retry_after_ms, deadline_ms - now_ms, _random.random())
                if delay_ms >= 0:
                    logger.debug("429 from %s; retrying in %dms (attempt %d)", url, delay_ms, attempt)
                    time.sleep(delay_ms / 1000)
                    continue
            self._handle_error(response)
            return response

    def _resolve_audience(self) -> str | None:
        """The venue's DID, for audience-bound auth — resolved once and cached.

        Prefers the DID from ``GET /api/v1/status`` (one request that also
        carries the venue name and readiness); falls back to the public
        ``/.well-known/did.json`` for an auth-gated venue whose status endpoint
        is not anonymously readable. Returns ``None`` if neither resolves (the
        token is then sent without an ``aud``, i.e. a plain self-issued identity)."""
        if self._venue_did is not None:
            return self._venue_did
        if self._resolving_did:
            # Re-entrant: this call is the status/did.json bootstrap itself. It
            # carries no audience to avoid an infinite loop (both are public).
            return None
        self._resolving_did = True
        try:
            did: str | None = None
            try:
                did = self.get_status().did
            except Exception as exc:  # noqa: BLE001 — status may be auth-gated (401)
                logger.debug("status DID unavailable, falling back to did.json: %s", exc)
            if not did:
                did = self.get_did_document().id
            self._venue_did = did
        except Exception as exc:  # noqa: BLE001 — best-effort; auth still works without aud
            logger.debug("Could not resolve venue DID for audience: %s", exc)
            return None
        finally:
            self._resolving_did = False
        return self._venue_did

    def venue_did(self) -> str | None:
        """The venue's DID — resolved once from ``GET /api/v1/status`` (falling
        back to the DID document) and cached. This is the same value used as the
        audience-bound ``aud``, so the venue's reported identity and the token
        audience never disagree."""
        return self._resolve_audience()

    def _apply_auth(self, kwargs: dict[str, Any]) -> None:
        """Inject authentication headers into request kwargs."""
        auth = self._config.auth
        if auth is None:
            return
        audience = self._resolve_audience() if auth.wants_audience else None
        auth_headers: dict[str, str] = {}
        auth.apply(auth_headers, audience=audience)
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
        if response.status_code == 429:
            try:
                retry_after = max(1, int(float(response.headers.get("Retry-After", "1"))))
            except ValueError:
                retry_after = 1
            raise RateLimitError(message, retry_after, response_body=body)
        raise GridError(
            status_code=response.status_code,
            message=message,
            response_body=body,
        )
