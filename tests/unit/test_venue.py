"""Tests for Venue operations."""

from __future__ import annotations

import httpx
import pytest

from covia import (
    Asset,
    AssetNotFoundError,
    CoviaConnectionError,
    CoviaTimeoutError,
    Grid,
    GridError,
    Job,
    JobNotFoundError,
    JobStatus,
    NotFoundError,
    Venue,
)
from tests.conftest import VENUE_URL

API_BASE = f"{VENUE_URL}/api/v1/"

# Raw metadata strings and their content-addressed IDs for deterministic tests.
_RAW_TEST_ASSET = '{"name": "Test Asset", "description": "A test"}'
_ID_TEST_ASSET = Asset.compute_id(_RAW_TEST_ASSET)

_RAW_TEST_ASSET_NAME_ONLY = '{"name": "Test Asset"}'
_ID_TEST_ASSET_NAME_ONLY = Asset.compute_id(_RAW_TEST_ASSET_NAME_ONLY)

_RAW_NEW_ASSET = '{"name": "New Asset"}'
_ID_NEW_ASSET = Asset.compute_id(_RAW_NEW_ASSET)

_RAW_FROM_ASSET = '{"name": "From Asset"}'
_ID_FROM_ASSET = Asset.compute_id(_RAW_FROM_ASSET)


class TestVenueStatus:
    def test_status(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}status",
            json={"did": "did:web:test.covia.ai", "url": VENUE_URL, "name": "Test Venue"},
        )
        status = venue.status()
        assert status.did == "did:web:test.covia.ai"
        assert status.name == "Test Venue"

    def test_url_property(self, venue):
        assert venue.url == VENUE_URL

    def test_repr(self, venue):
        assert "test.covia.ai" in repr(venue)


class TestVenueReady:
    def test_ready_immediately(self, httpx_mock, venue):
        httpx_mock.add_response(url=f"{API_BASE}status", json={"status": "OK", "name": "Test Venue"})
        status = venue.wait_until_ready(timeout=5, poll_interval=0)
        assert status.status == "OK"

    def test_ready_when_no_status_field(self, httpx_mock, venue):
        # Venues that omit an explicit status field are ready as soon as
        # /api/v1/status responds at all.
        httpx_mock.add_response(url=f"{API_BASE}status", json={"name": "Test Venue"})
        status = venue.wait_until_ready(timeout=5, poll_interval=0)
        assert status.name == "Test Venue"

    def test_retries_until_ready(self, httpx_mock, venue):
        # Connection refused twice (venue still booting), then OK.
        httpx_mock.add_exception(httpx.ConnectError("refused"), url=f"{API_BASE}status")
        httpx_mock.add_exception(httpx.ConnectError("refused"), url=f"{API_BASE}status")
        httpx_mock.add_response(url=f"{API_BASE}status", json={"status": "OK"})
        status = venue.wait_until_ready(timeout=5, poll_interval=0)
        assert status.status == "OK"

    def test_waits_for_ok_status(self, httpx_mock, venue):
        # HTTP 200 but invoke layer still warming, then OK.
        httpx_mock.add_response(url=f"{API_BASE}status", json={"status": "STARTING"})
        httpx_mock.add_response(url=f"{API_BASE}status", json={"status": "OK"})
        status = venue.wait_until_ready(timeout=5, poll_interval=0)
        assert status.status == "OK"

    def test_timeout_raises(self, httpx_mock, venue):
        # Never ready → CoviaTimeoutError. timeout=0 → one attempt then raise.
        httpx_mock.add_exception(httpx.ConnectError("refused"), url=f"{API_BASE}status")
        with pytest.raises(CoviaTimeoutError):
            venue.wait_until_ready(timeout=0, poll_interval=0)


class TestVenueAssets:
    def test_list_assets(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}assets?offset=0",
            json={"items": ["abc123", "def456"], "total": 2, "offset": 0, "limit": 100},
        )
        result = venue.list_assets()
        assert len(result.items) == 2
        assert result.total == 2

    def test_get_asset(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}assets/{_ID_TEST_ASSET}",
            text=_RAW_TEST_ASSET,
            headers={"content-type": "application/json"},
        )
        asset = venue.get_asset(_ID_TEST_ASSET)
        assert isinstance(asset, Asset)
        assert asset.id == _ID_TEST_ASSET
        assert asset.name == "Test Asset"

    def test_get_asset_preserves_raw_metadata(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}assets/{_ID_TEST_ASSET_NAME_ONLY}",
            text=_RAW_TEST_ASSET_NAME_ONLY,
            headers={"content-type": "application/json"},
        )
        asset = venue.get_asset(_ID_TEST_ASSET_NAME_ONLY)
        assert asset.metadata_raw is not None
        assert '"name"' in asset.metadata_raw
        assert '"Test Asset"' in asset.metadata_raw

    def test_get_asset_by_lattice_path(self, httpx_mock, venue):
        # A mutable lattice path is resolved by the venue (covia#150) — sent as a
        # plain GET; no client-side hash check, id is the resolved canonical hash.
        raw = '{"name": "Foo", "operation": {}}'
        httpx_mock.add_response(
            url=f"{API_BASE}assets/w/my-assets/foo",
            text=raw,
            headers={"content-type": "application/json"},
        )
        asset = venue.get_asset("w/my-assets/foo")
        assert asset.name == "Foo"
        assert asset.is_operation
        assert asset.id == Asset.compute_id(raw)

    def test_get_asset_hash_mismatch_raises(self, httpx_mock, venue):
        # Integrity check still applies for content-addressed refs.
        httpx_mock.add_response(
            url=f"{API_BASE}assets/{_ID_TEST_ASSET}",
            text='{"name": "Tampered"}',
            headers={"content-type": "application/json"},
        )
        with pytest.raises(ValueError, match="mismatch"):
            venue.get_asset(_ID_TEST_ASSET)

    def test_register_with_dict(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}assets",
            text=f'"{_ID_NEW_ASSET}"',
            status_code=201,
        )
        httpx_mock.add_response(
            url=f"{API_BASE}assets/{_ID_NEW_ASSET}",
            text=_RAW_NEW_ASSET,
            headers={"content-type": "application/json"},
        )
        asset = venue.register({"name": "New Asset"})
        assert isinstance(asset, Asset)
        assert asset.id == _ID_NEW_ASSET
        assert asset.name == "New Asset"
        assert asset.venue is venue

    def test_register_with_asset(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}assets",
            text=f'"{_ID_FROM_ASSET}"',
            status_code=201,
        )
        httpx_mock.add_response(
            url=f"{API_BASE}assets/{_ID_FROM_ASSET}",
            text=_RAW_FROM_ASSET,
            headers={"content-type": "application/json"},
        )
        unregistered = Asset({"name": "From Asset"})
        asset = venue.register(unregistered)
        assert isinstance(asset, Asset)
        assert asset.id == _ID_FROM_ASSET
        assert asset.name == "From Asset"
        assert asset.venue is venue

    def test_get_asset_content(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}assets/abc123/content",
            content=b"binary content here",
        )
        content = venue.get_asset_content("abc123")
        assert content == b"binary content here"

    def test_put_asset_content(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}assets/abc123/content",
            text='"sha256hash"',
        )
        result = venue.put_asset_content("abc123", b"data")
        assert result == "sha256hash"


class TestVenueInvoke:
    def test_invoke_returns_job(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}invoke",
            json={"id": "job001", "status": "PENDING"},
            status_code=201,
        )
        job = venue.invoke("my-operation", {"x": 1})
        assert isinstance(job, Job)
        assert job.id == "job001"
        assert job.status == JobStatus.PENDING

    def test_invoke_complete_inline(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}invoke",
            json={"id": "job002", "status": "COMPLETE", "output": {"result": 42}},
            status_code=201,
        )
        job = venue.invoke("fast-op")
        assert job.is_complete
        assert job.output == {"result": 42}

    def test_run_returns_output(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}invoke",
            json={"id": "job003", "status": "COMPLETE", "output": "hello"},
            status_code=201,
        )
        result = venue.run("echo", {"text": "hello"})
        assert result == "hello"


class TestVenueJobs:
    def test_get_job(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}jobs/job001",
            json={"id": "job001", "status": "STARTED"},
        )
        job = venue.get_job("job001")
        assert job.id == "job001"
        assert job.status == JobStatus.STARTED

    def test_list_jobs(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}jobs",
            json=["job001", "job002"],
        )
        jobs = venue.list_jobs()
        assert len(jobs) == 2

    def test_cancel_job(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}jobs/job001/cancel",
            json={"id": "job001", "status": "CANCELLED"},
        )
        result = venue.cancel_job("job001")
        assert result.status == JobStatus.CANCELLED

    def test_delete_job(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}jobs/job001/delete",
            text="",
        )
        venue.delete_job("job001")  # Should not raise


class TestVenueDIDCaching:
    def test_did_fetches_on_first_access(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{VENUE_URL}/.well-known/did.json",
            json={"id": "did:web:test.covia.ai"},
        )
        assert venue.did == "did:web:test.covia.ai"

    def test_did_caches_after_first_access(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{VENUE_URL}/.well-known/did.json",
            json={"id": "did:web:test.covia.ai"},
        )
        # First access fetches
        did1 = venue.did
        # Second access uses cache — no additional HTTP request
        did2 = venue.did
        assert did1 == did2 == "did:web:test.covia.ai"
        # Only one request should have been made
        assert len(httpx_mock.get_requests()) == 1

    def test_did_document_not_affected_by_cache(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{VENUE_URL}/.well-known/did.json",
            json={"id": "did:web:test.covia.ai", "@context": "https://www.w3.org/ns/did/v1"},
        )
        # did_document() always fetches the full document, independent of did cache
        doc = venue.did_document()
        assert doc.id == "did:web:test.covia.ai"
        assert doc.context == "https://www.w3.org/ns/did/v1"


class TestVenueDiscovery:
    def test_did_document(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{VENUE_URL}/.well-known/did.json",
            json={"id": "did:web:test.covia.ai", "@context": "https://www.w3.org/ns/did/v1"},
        )
        doc = venue.did_document()
        assert doc.id == "did:web:test.covia.ai"

    def test_mcp_discovery(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{VENUE_URL}/.well-known/mcp",
            json={"mcp_version": "0.12", "server_url": VENUE_URL},
        )
        mcp = venue.mcp_discovery()
        assert mcp.mcp_version == "0.12"

    def test_agent_card(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{VENUE_URL}/.well-known/agent-card.json",
            json={"agentProvider": {"name": "Covia"}},
        )
        card = venue.agent_card()
        assert card.agentProvider is not None
        assert card.agentProvider["name"] == "Covia"


class TestVenueErrorHandling:
    def test_get_asset_404_raises_asset_not_found(self, httpx_mock, venue):
        httpx_mock.add_response(url=f"{API_BASE}assets/missing", status_code=404, json={"error": "not found"})
        with pytest.raises(AssetNotFoundError) as exc_info:
            venue.get_asset("missing")
        assert exc_info.value.asset_id == "missing"

    def test_get_asset_content_404_raises_asset_not_found(self, httpx_mock, venue):
        httpx_mock.add_response(url=f"{API_BASE}assets/missing/content", status_code=404)
        with pytest.raises(AssetNotFoundError):
            venue.get_asset_content("missing")

    def test_asset_not_found_is_catchable_as_not_found(self, httpx_mock, venue):
        httpx_mock.add_response(url=f"{API_BASE}assets/missing", status_code=404)
        with pytest.raises(NotFoundError):
            venue.get_asset("missing")

    def test_asset_not_found_is_catchable_as_api_error(self, httpx_mock, venue):
        httpx_mock.add_response(url=f"{API_BASE}assets/missing", status_code=404)
        with pytest.raises(GridError):
            venue.get_asset("missing")

    def test_get_asset_500_raises_api_error(self, httpx_mock, venue):
        httpx_mock.add_response(url=f"{API_BASE}assets/abc", status_code=500, json={"error": "boom"})
        with pytest.raises(GridError) as exc_info:
            venue.get_asset("abc")
        assert not isinstance(exc_info.value, AssetNotFoundError)
        assert exc_info.value.status_code == 500

    def test_get_job_404_raises_job_not_found(self, httpx_mock, venue):
        httpx_mock.add_response(url=f"{API_BASE}jobs/missing", status_code=404, json={"error": "not found"})
        with pytest.raises(JobNotFoundError) as exc_info:
            venue.get_job("missing")
        assert exc_info.value.job_id == "missing"

    def test_cancel_job_404_raises_job_not_found(self, httpx_mock, venue):
        httpx_mock.add_response(url=f"{API_BASE}jobs/missing/cancel", status_code=404)
        with pytest.raises(JobNotFoundError):
            venue.cancel_job("missing")

    def test_job_not_found_is_catchable_as_not_found(self, httpx_mock, venue):
        httpx_mock.add_response(url=f"{API_BASE}jobs/missing", status_code=404)
        with pytest.raises(NotFoundError):
            venue.get_job("missing")

    def test_job_not_found_is_catchable_as_api_error(self, httpx_mock, venue):
        httpx_mock.add_response(url=f"{API_BASE}jobs/missing", status_code=404)
        with pytest.raises(GridError):
            venue.get_job("missing")

    def test_connection_error_is_standard(self):
        assert issubclass(CoviaConnectionError, ConnectionError)

    def test_timeout_error_is_standard(self):
        assert issubclass(CoviaTimeoutError, TimeoutError)


class TestVenueContextManager:
    def test_context_manager(self, httpx_mock):
        with Grid.connect(VENUE_URL) as v:
            assert isinstance(v, Venue)
