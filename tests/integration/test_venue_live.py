"""Basic integration tests against a live Covia venue.

These tests are skipped by default. Run with::

    pytest -m integration

Set ``COVIA_VENUE_URL`` to target a specific venue.
"""

from __future__ import annotations

import os

import pytest

from covia import Grid, __version__

VENUE_URL = os.environ.get("COVIA_VENUE_URL", "https://venue-4.covia.ai")


pytestmark = pytest.mark.integration


@pytest.fixture
def venue():
    v = Grid.connect(VENUE_URL)
    yield v
    v.close()


def test_status(venue):
    status = venue.status()
    assert status is not None
    assert status.did is not None
    assert status.version is not None
    if os.environ.get("COVIA_REQUIRE_VERSION_MATCH") == "1":
        assert status.version == __version__


def test_did_document(venue):
    doc = venue.did_document()
    assert doc.id.startswith("did:")


def test_list_assets(venue):
    result = venue.list_assets(limit=10)
    assert result.items is not None
    assert result.total >= 0


def test_list_jobs(venue):
    # Anonymous callers may not be allowed to list jobs on some venues.
    # If the venue enforces auth for this endpoint, skip cleanly rather
    # than failing the suite.
    try:
        jobs = venue.list_jobs()
    except Exception as e:
        pytest.skip(f"list_jobs not available to anonymous caller: {e}")
    assert isinstance(jobs, list)
