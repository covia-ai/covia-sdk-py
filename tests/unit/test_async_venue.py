"""Tests for the async Venue API."""

from __future__ import annotations

import httpx
import pytest

from covia import CoviaTimeoutError, JobStatus
from covia.async_api.job import AsyncJob
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
