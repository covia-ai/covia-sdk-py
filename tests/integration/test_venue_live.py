"""Integration tests against a live Covia venue.

These tests are skipped by default. Run with:
    pytest -m integration

Set the COVIA_VENUE_URL environment variable to specify the venue.
"""

from __future__ import annotations

import os

import pytest

from covia import Grid

VENUE_URL = os.environ.get("COVIA_VENUE_URL", "https://venue-test.covia.ai")


pytestmark = pytest.mark.integration


@pytest.fixture
def venue():
    v = Grid.connect(VENUE_URL)
    yield v
    v.close()


def test_status(venue):
    status = venue.status()
    assert status is not None


def test_list_assets(venue):
    result = venue.list_assets(limit=10)
    assert result.items is not None
    assert result.total >= 0


def test_list_jobs(venue):
    jobs = venue.list_jobs()
    assert isinstance(jobs, list)
