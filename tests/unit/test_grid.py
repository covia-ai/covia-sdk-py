"""Tests for Grid connection and URL/DID resolution."""

from __future__ import annotations

import pytest

from covia import Grid, Venue
from covia._transport import resolve_connection


class TestResolveConnection:
    def test_https_url(self):
        assert resolve_connection("https://venue.covia.ai") == "https://venue.covia.ai"

    def test_http_url(self):
        assert resolve_connection("http://localhost:8080") == "http://localhost:8080"

    def test_did_web(self):
        assert resolve_connection("did:web:venue.covia.ai") == "https://venue.covia.ai"

    def test_did_web_with_whitespace(self):
        assert resolve_connection("  did:web:example.com  ") == "https://example.com"

    def test_unknown_format_raises(self):
        with pytest.raises(ValueError, match="Unrecognised"):
            resolve_connection("ftp://bad")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            resolve_connection("")


class TestGridConnect:
    def test_connect_returns_venue(self):
        venue = Grid.connect("https://test.covia.ai")
        assert isinstance(venue, Venue)
        venue.close()

    def test_connect_with_did(self):
        venue = Grid.connect("did:web:test.covia.ai")
        assert isinstance(venue, Venue)
        assert venue.url == "https://test.covia.ai"
        venue.close()

    def test_connect_with_headers(self):
        venue = Grid.connect(
            "https://test.covia.ai",
            headers={"Authorization": "Bearer token123"},
        )
        assert isinstance(venue, Venue)
        venue.close()

    def test_connect_with_timeout(self):
        venue = Grid.connect("https://test.covia.ai", timeout=5.0)
        assert isinstance(venue, Venue)
        venue.close()

    def test_connect_bad_url_raises(self):
        with pytest.raises(ValueError):
            Grid.connect("not-a-url")
