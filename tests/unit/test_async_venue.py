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


class TestAsyncJobInteractive:
    async def test_needs_input_and_auth(self, async_venue):
        job = AsyncJob(data=JobData(id="j", status=JobStatus.INPUT_REQUIRED), venue=async_venue)
        assert job.needs_input and not job.needs_auth and job.is_paused
        job2 = AsyncJob(data=JobData(id="j", status=JobStatus.AUTH_REQUIRED), venue=async_venue)
        assert job2.needs_auth and not job2.needs_input

    async def test_pause_resume(self, httpx_mock, async_venue):
        job = AsyncJob(data=JobData(id="job001", status=JobStatus.STARTED), venue=async_venue)
        httpx_mock.add_response(url=f"{API_BASE}jobs/job001/pause", json={"id": "job001", "status": "PAUSED"})
        await job.pause()
        assert job.status == JobStatus.PAUSED
        httpx_mock.add_response(url=f"{API_BASE}jobs/job001/resume", json={"id": "job001", "status": "STARTED"})
        await job.resume()
        assert job.status == JobStatus.STARTED

    async def test_send_message(self, httpx_mock, async_venue):
        job = AsyncJob(data=JobData(id="job001", status=JobStatus.INPUT_REQUIRED), venue=async_venue)
        httpx_mock.add_response(
            url=f"{API_BASE}jobs/job001",
            method="POST",
            json={"status": "queued", "queueDepth": 2},
            status_code=202,
        )
        result = await job.send_message({"answer": "yes"})
        assert result == {"status": "queued", "queueDepth": 2}


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


class TestAsyncStreaming:
    async def test_stream_returns_async_iterator_not_coroutine(self, async_venue):
        # Regression: stream_job_events / AsyncJob.stream must return an async
        # iterator to `async for` over — not a coroutine you have to await first.
        import inspect
        from collections.abc import AsyncIterator

        venue_gen = async_venue.stream_job_events("job-1")
        assert not inspect.iscoroutine(venue_gen)
        assert isinstance(venue_gen, AsyncIterator)
        await venue_gen.aclose()

        job = AsyncJob(data=JobData(id="job-1", status=JobStatus.STARTED), venue=async_venue)
        job_gen = job.stream()
        assert not inspect.iscoroutine(job_gen)
        assert isinstance(job_gen, AsyncIterator)
        await job_gen.aclose()
