"""Tests for Venue operations."""

from __future__ import annotations

from covia import Asset, Grid, Job, JobStatus, Venue
from tests.conftest import VENUE_URL

API_BASE = f"{VENUE_URL}/api/v1/"


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
            url=f"{API_BASE}assets/abc123",
            json={"name": "Test Asset", "description": "A test"},
        )
        asset = venue.get_asset("abc123")
        assert isinstance(asset, Asset)
        assert asset.id == "abc123"
        assert asset.name == "Test Asset"

    def test_get_asset_preserves_raw_metadata(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}assets/abc123",
            json={"name": "Test Asset"},
        )
        asset = venue.get_asset("abc123")
        assert asset.metadata_raw is not None
        assert '"name"' in asset.metadata_raw
        assert '"Test Asset"' in asset.metadata_raw

    def test_register_asset(self, httpx_mock, venue):
        httpx_mock.add_response(
            url=f"{API_BASE}assets",
            text='"abc123"',
            status_code=201,
        )
        asset_id = venue.register_asset({"name": "New Asset"})
        assert asset_id == "abc123"

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


class TestVenueContextManager:
    def test_context_manager(self, httpx_mock):
        with Grid.connect(VENUE_URL) as v:
            assert isinstance(v, Venue)
