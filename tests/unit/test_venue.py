"""Tests for Venue operations."""

from __future__ import annotations

import json

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
_ID_TEST_ASSET = "1" * 64

_RAW_TEST_ASSET_NAME_ONLY = '{"name": "Test Asset"}'
_ID_TEST_ASSET_NAME_ONLY = "2" * 64

_RAW_NEW_ASSET = '{"name": "New Asset"}'
_ID_NEW_ASSET = "3" * 64

_RAW_FROM_ASSET = '{"name": "From Asset"}'
_ID_FROM_ASSET = "4" * 64


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
            headers={"content-type": "application/json", "ETag": '"0x' + "5" * 64 + '"'},
        )
        asset = venue.get_asset("w/my-assets/foo")
        assert asset.name == "Foo"
        assert asset.is_operation
        assert asset.id == "5" * 64

    def test_get_asset_hash_mismatch_raises(self, httpx_mock, venue):
        # A venue response must identify the requested immutable asset.
        httpx_mock.add_response(
            url=f"{API_BASE}assets/{_ID_TEST_ASSET}",
            text='{"name": "Different"}',
            headers={"content-type": "application/json", "ETag": '"0x' + "6" * 64 + '"'},
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

    def test_pin_asset(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}run",
            json={"path": "did:key:z6Mk.../a/deadbeef", "hash": "deadbeef"},
            status_code=201,
        )
        result = venue.pin_asset("w/my-assets/foo")
        assert result.hash == "deadbeef"
        assert result.path == "did:key:z6Mk.../a/deadbeef"
        body = json.loads(httpx_mock.get_requests()[-1].content)
        assert body["operation"] == "v/ops/asset/pin"
        assert body["input"] == {"path": "w/my-assets/foo"}


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
            url=f"{API_BASE}run",
            json="hello",
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
            url=f"{API_BASE}jobs?offset=0&limit=1000",
            json=["job001", "job002"],
        )
        jobs = venue.list_jobs()
        assert len(jobs) == 2

    def test_list_jobs_envelope(self, httpx_mock, venue):
        # Venue 0.6.0 paged envelope (covia#229) — same call, same result.
        httpx_mock.add_response(
            url=f"{API_BASE}jobs?offset=0&limit=1000",
            json={"items": ["job001", "job002"], "total": 2, "offset": 0, "limit": 1000},
        )
        jobs = venue.list_jobs()
        assert jobs == ["job001", "job002"]

    def test_list_jobs_collects_all_pages(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}jobs?offset=0&limit=1000",
            json={"items": ["job001", "job002"], "total": 3, "offset": 0, "limit": 2},
        )
        httpx_mock.add_response(
            url=f"{API_BASE}jobs?offset=2&limit=1000",
            json={"items": ["job003"], "total": 3, "offset": 2, "limit": 2},
        )
        assert venue.list_jobs() == ["job001", "job002", "job003"]

    def test_cancel_job(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}jobs/job001/cancel",
            json={"id": "job001", "status": "CANCELLED"},
        )
        result = venue.cancel_job("job001")
        assert result.status == JobStatus.CANCELLED

    def test_cancel_job_with_reason(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}jobs/job001/cancel",
            json={"id": "job001", "status": "CANCELLED"},
        )
        venue.cancel_job("job001", reason="superseded")
        assert json.loads(httpx_mock.get_requests()[-1].content) == {"reason": "superseded"}

    def test_delete_job(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}jobs/job001/delete",
            text="",
        )
        venue.delete_job("job001")  # Should not raise


class TestVenueDIDCaching:
    def test_did_fetches_on_first_access(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{VENUE_URL}/api/v1/status",
            json={"name": "Test", "did": "did:web:test.covia.ai"},
        )
        assert venue.did == "did:web:test.covia.ai"

    def test_did_caches_after_first_access(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{VENUE_URL}/api/v1/status",
            json={"name": "Test", "did": "did:web:test.covia.ai"},
        )
        # First access resolves via /status; the second uses the cached DID
        did1 = venue.did
        did2 = venue.did
        assert did1 == did2 == "did:web:test.covia.ai"
        # Only one request should have been made (cached thereafter)
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
            json={
                "name": "probe-agent",
                "provider": {"organization": "Covia", "url": "https://covia.ai"},
                "preferredTransport": "JSONRPC",
            },
        )
        card = venue.agent_card()
        assert card.name == "probe-agent"
        assert card.provider is not None
        assert card.provider["organization"] == "Covia"
        assert card.preferredTransport == "JSONRPC"


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


def test_filtered_assets_and_adapter_metadata(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}assets?offset=2&kind=data&limit=3",
        json={"items": ["did:web:test.covia.ai/a/abc"], "total": 9, "offset": 2, "limit": 3},
    )
    page = venue.list_assets(offset=2, limit=3, kind="data")
    assert page.total == 9
    assert page.items == ["did:web:test.covia.ai/a/abc"]
    metadata = {"echo": {"name": "Echo", "operation": {"adapter": "test:echo", "input": {}}}}
    httpx_mock.add_response(url=f"{API_BASE}adapters/test/operations", json=metadata)
    assert venue.get_adapter_operations("test") == metadata
    httpx_mock.add_response(url=f"{API_BASE}adapters/missing/operations", status_code=404, json={"error": "inactive"})
    with pytest.raises(GridError) as exc:
        venue.get_adapter_operations("missing")
    assert exc.value.status_code == 404


@pytest.mark.parametrize("ref", ["a/" + "a" * 64, "0x" + "A" * 64, "w/asset", "did:web:owner/a/" + "a" * 64])
def test_asset_uses_cad3_etag_not_json_bytes(httpx_mock, venue, ref):
    raw = '{ "name": "Formatting does not define identity" }'
    httpx_mock.add_response(
        url=f"{API_BASE}assets/{ref}",
        text=raw,
        headers={"ETag": '"0x' + "a" * 64 + '"'},
    )
    asset = venue.get_asset(ref)
    assert asset.id == "a" * 64
    assert asset.metadata_raw == raw


@pytest.mark.parametrize("etag", ['W/"' + "a" * 64 + '"', '"not-a-hash"', '"0x' + "b" * 64 + '"'])
def test_asset_rejects_invalid_or_conflicting_etag(httpx_mock, venue, etag):
    ref = "a" * 64
    httpx_mock.add_response(url=f"{API_BASE}assets/{ref}", json={}, headers={"ETag": etag})
    with pytest.raises(ValueError):
        venue.get_asset(ref)
