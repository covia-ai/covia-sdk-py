"""Tests for Asset metadata, content, and invocation."""

from __future__ import annotations

import pytest

from covia import Asset
from tests.conftest import VENUE_URL

API_BASE = f"{VENUE_URL}/api/v1/"


class TestAssetProperties:
    def test_id(self):
        asset = Asset(id="abc123", metadata={"name": "Test"})
        assert asset.id == "abc123"

    def test_name(self):
        asset = Asset(id="a1", metadata={"name": "My Asset"})
        assert asset.name == "My Asset"

    def test_description(self):
        asset = Asset(id="a1", metadata={"description": "A test asset"})
        assert asset.description == "A test asset"

    def test_content_type(self):
        asset = Asset(id="a1", metadata={"content-type": "application/json"})
        assert asset.content_type == "application/json"

    def test_metadata_raw_when_provided(self):
        raw = '{"name": "Test"}'
        asset = Asset(id="a1", metadata={"name": "Test"}, metadata_raw=raw)
        assert asset.metadata_raw == raw

    def test_metadata_raw_none_by_default(self):
        asset = Asset(id="a1", metadata={"name": "Test"})
        assert asset.metadata_raw is None

    def test_is_operation_true(self):
        asset = Asset(id="a1", metadata={"operation": {"type": "tool"}})
        assert asset.is_operation

    def test_is_operation_false(self):
        asset = Asset(id="a1", metadata={"name": "data"})
        assert not asset.is_operation

    def test_repr_with_name(self):
        asset = Asset(id="abc123", metadata={"name": "Test"})
        assert "Test" in repr(asset)

    def test_repr_without_name(self):
        asset = Asset(id="abcdef1234567890", metadata={})
        assert "abcdef1234567890" in repr(asset)

    def test_equality(self):
        a1 = Asset(id="abc", metadata={})
        a2 = Asset(id="abc", metadata={"name": "different"})
        a3 = Asset(id="xyz", metadata={})
        assert a1 == a2
        assert a1 != a3
        assert a1 != "abc"

    def test_hash(self):
        a1 = Asset(id="abc", metadata={})
        a2 = Asset(id="abc", metadata={"name": "other"})
        assert hash(a1) == hash(a2)
        assert {a1, a2} == {a1}


class TestAssetVenue:
    def test_venue_property(self, venue):
        asset = Asset(id="a1", metadata={}, venue=venue)
        assert asset.venue is venue

    def test_no_venue(self):
        asset = Asset(id="a1", metadata={})
        assert asset.venue is None

    def test_did_url_with_venue(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{VENUE_URL}/.well-known/did.json",
            json={"id": "did:web:test.covia.ai"},
        )
        asset = Asset(id="abc123", metadata={}, venue=venue)
        assert asset.did_url == "did:web:test.covia.ai/a/abc123"

    def test_did_url_without_venue(self):
        asset = Asset(id="abc123", metadata={})
        assert asset.did_url is None


class TestAssetContent:
    def test_get_content(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}assets/abc123/content",
            content=b"file data",
        )
        asset = Asset(id="abc123", metadata={}, venue=venue)
        assert asset.get_content() == b"file data"

    def test_get_content_no_venue_raises(self):
        asset = Asset(id="abc123", metadata={})
        with pytest.raises(ValueError, match="no attached venue"):
            asset.get_content()

    def test_put_content(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}assets/abc123/content",
            text='"hash123"',
        )
        asset = Asset(id="abc123", metadata={}, venue=venue)
        result = asset.put_content(b"new data")
        assert result == "hash123"

    def test_put_content_no_venue_raises(self):
        asset = Asset(id="abc123", metadata={})
        with pytest.raises(ValueError, match="no attached venue"):
            asset.put_content(b"data")


class TestAssetInvoke:
    def test_invoke(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}invoke",
            json={"id": "job001", "status": "COMPLETE", "output": "result"},
            status_code=201,
        )
        asset = Asset(id="abc123", metadata={"operation": {}}, venue=venue)
        job = asset.invoke({"x": 1})
        assert job.is_complete

    def test_invoke_no_venue_raises(self):
        asset = Asset(id="abc123", metadata={"operation": {}})
        with pytest.raises(ValueError, match="no attached venue"):
            asset.invoke()

    def test_run(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}invoke",
            json={"id": "job001", "status": "COMPLETE", "output": 99},
            status_code=201,
        )
        asset = Asset(id="abc123", metadata={"operation": {}}, venue=venue)
        result = asset.run({"x": 1})
        assert result == 99

    def test_run_no_venue_raises(self):
        asset = Asset(id="abc123", metadata={"operation": {}})
        with pytest.raises(ValueError, match="no attached venue"):
            asset.run()
