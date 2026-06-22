"""Shared test fixtures for the Covia SDK test suite."""

from __future__ import annotations

import pytest

from covia import Grid
from covia.async_api import AsyncGrid

VENUE_URL = "https://test.covia.ai"


@pytest.fixture
def venue(httpx_mock):
    """A Venue instance backed by a mocked HTTP transport."""
    v = Grid.connect(VENUE_URL)
    yield v
    v.close()


@pytest.fixture
async def async_venue(httpx_mock):
    """An AsyncVenue instance backed by a mocked HTTP transport."""
    v = AsyncGrid.connect(VENUE_URL)
    yield v
    await v.aclose()
