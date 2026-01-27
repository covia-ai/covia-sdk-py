"""Shared test fixtures for the Covia SDK test suite."""

from __future__ import annotations

import pytest

from covia import Grid

VENUE_URL = "https://test.covia.ai"


@pytest.fixture
def venue(httpx_mock):
    """A Venue instance backed by a mocked HTTP transport."""
    v = Grid.connect(VENUE_URL)
    yield v
    v.close()
