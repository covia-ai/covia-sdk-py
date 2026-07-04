"""Tests for the async Venue API."""

from __future__ import annotations

import httpx
import jwt
import pytest

from covia import CoviaTimeoutError, JobStatus
from covia.async_api import AsyncGrid
from covia.async_api.job import AsyncJob
from covia.auth import Ed25519Auth
from covia.models import JobData
from tests.conftest import VENUE_URL

API_BASE = f"{VENUE_URL}/api/v1/"


class TestAsyncVenueReady:
    async def test_ready_immediately(self, httpx_mock, async_venue):
        httpx_mock.add_response(url=f"{API_BASE}status", json={"status": "OK"})
        status = await async_venue.wait_until_ready(timeout=5, poll_interval=0)
        assert status.status == "OK"

    async def test_retries_until_ready(self, httpx_mock, async_venue):
        httpx_mock.add_exception(httpx.ConnectError("refused"), url=f"{API_BASE}status")
        httpx_mock.add_response(url=f"{API_BASE}status", json={"status": "OK"})
        status = await async_venue.wait_until_ready(timeout=5, poll_interval=0)
        assert status.status == "OK"

    async def test_timeout_raises(self, httpx_mock, async_venue):
        httpx_mock.add_exception(httpx.ConnectError("refused"), url=f"{API_BASE}status")
        with pytest.raises(CoviaTimeoutError):
            await async_venue.wait_until_ready(timeout=0, poll_interval=0)


class TestAsyncJobWait:
    async def test_polls_until_complete(self, httpx_mock, async_venue):
        job = AsyncJob(data=JobData(id="job001", status=JobStatus.PENDING), venue=async_venue)
        httpx_mock.add_response(url=f"{API_BASE}jobs/job001", json={"id": "job001", "status": "STARTED"})
        httpx_mock.add_response(
            url=f"{API_BASE}jobs/job001", json={"id": "job001", "status": "COMPLETE", "output": "result"}
        )
        await job.wait(timeout=10)
        assert job.is_complete
        assert job.output == "result"

    async def test_timeout_raises(self, httpx_mock, async_venue):
        # Always STARTED → wait() must time out (wall-clock, via time.monotonic).
        job = AsyncJob(data=JobData(id="job001", status=JobStatus.PENDING), venue=async_venue)
        httpx_mock.add_response(url=f"{API_BASE}jobs/job001", json={"id": "job001", "status": "STARTED"})
        with pytest.raises(CoviaTimeoutError, match="did not finish"):
            await job.wait(timeout=0.1)


class TestAsyncVenueGetAsset:
    async def test_get_asset_by_lattice_path(self, httpx_mock, async_venue):
        raw = '{"name": "Foo"}'
        httpx_mock.add_response(
            url=f"{API_BASE}assets/w/my-assets/foo",
            text=raw,
            headers={"content-type": "application/json"},
        )
        asset = await async_venue.get_asset("w/my-assets/foo")
        assert asset.name == "Foo"


class TestAsyncAuthAudience:
    async def test_audience_resolved_from_venue_did(self, httpx_mock):
        # Async parity: aud is the venue's reported DID, now resolved from
        # /api/v1/status, not the connection string; the auth object is not mutated.
        httpx_mock.add_response(url=f"{API_BASE}status", json={"name": "Test", "did": "did:web:test.covia.ai"})
        httpx_mock.add_response(url=f"{API_BASE}secrets", json={"items": [], "total": 0})
        auth = Ed25519Auth.generate()
        venue = AsyncGrid.connect(VENUE_URL, auth=auth)
        try:
            await venue.list_secrets()
        finally:
            await venue.aclose()
        assert auth.audience is None
        sec_req = next(r for r in httpx_mock.get_requests() if r.url.path.endswith("/secrets"))
        payload = jwt.decode(
            sec_req.headers["authorization"].removeprefix("Bearer "),
            options={"verify_signature": False},
        )
        assert payload["aud"] == "did:web:test.covia.ai"
        assert not any("did.json" in str(r.url) for r in httpx_mock.get_requests())
