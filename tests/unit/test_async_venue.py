"""Tests for the async Venue API."""

from __future__ import annotations

import httpx
import pytest

from covia import CoviaTimeoutError
from covia.async_api import AsyncGrid

VENUE_URL = "https://test.covia.ai"
API_BASE = f"{VENUE_URL}/api/v1/"


@pytest.fixture
async def async_venue():
    """An AsyncVenue backed by a mocked HTTP transport."""
    v = AsyncGrid.connect(VENUE_URL)
    yield v
    await v.aclose()


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
