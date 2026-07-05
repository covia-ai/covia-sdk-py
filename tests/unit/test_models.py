"""Tests for Pydantic request/response models."""

from __future__ import annotations

from covia.models import (
    AgentCard,
    AssetList,
    DIDDocument,
    ErrorResponse,
    JobData,
    MCPDiscovery,
    VenueStatus,
)
from covia.status import JobStatus


class TestVenueStatus:
    def test_basic(self):
        status = VenueStatus(did="did:web:test", url="https://test", name="Test")
        assert status.did == "did:web:test"
        assert status.name == "Test"

    def test_extra_fields_allowed(self):
        status = VenueStatus.model_validate({"did": "did:web:test", "url": "https://test", "custom_field": "value"})
        assert status.did == "did:web:test"


class TestAssetList:
    def test_basic(self):
        al = AssetList(items=["a", "b"], total=2, offset=0, limit=100)
        assert len(al.items) == 2
        assert al.total == 2


class TestJobData:
    def test_complete(self):
        jd = JobData(id="j1", status=JobStatus.COMPLETE, output=42)
        assert jd.status == JobStatus.COMPLETE
        assert jd.output == 42

    def test_failed(self):
        jd = JobData(id="j2", status=JobStatus.FAILED, error="bad input")
        assert jd.error == "bad input"

    def test_from_json(self):
        jd = JobData.model_validate({"id": "j3", "status": "STARTED"})
        assert jd.status == JobStatus.STARTED

    def test_extra_fields_allowed(self):
        jd = JobData.model_validate({"id": "j4", "status": "PENDING", "custom": "data"})
        assert jd.id == "j4"

    def test_default_status(self):
        jd = JobData()
        assert jd.status == JobStatus.PENDING


class TestErrorResponse:
    def test_basic(self):
        err = ErrorResponse(error="not found", data={"id": "x"})
        assert err.error == "not found"


class TestDIDDocument:
    def test_basic(self):
        doc = DIDDocument(id="did:web:test")
        assert doc.id == "did:web:test"

    def test_context_alias(self):
        doc = DIDDocument.model_validate({"id": "did:web:test", "@context": "https://www.w3.org/ns/did/v1"})
        assert doc.context == "https://www.w3.org/ns/did/v1"

    def test_extra_fields(self):
        doc = DIDDocument.model_validate({"id": "did:web:test", "verificationMethod": []})
        assert doc.id == "did:web:test"


class TestMCPDiscovery:
    def test_basic(self):
        mcp = MCPDiscovery(mcp_version="0.12", server_url="https://test")
        assert mcp.mcp_version == "0.12"


class TestAgentCard:
    def test_basic(self):
        card = AgentCard(
            name="probe-agent",
            description="probe",
            version="0.3.0",
            provider={"organization": "Covia", "url": "https://covia.ai"},
            capabilities={"streaming": True},
            defaultInputModes=["text/plain"],
            skills=[],
            supportedInterfaces=[{"protocolBinding": "JSONRPC", "url": "http://x/a2a"}],
            preferredTransport="JSONRPC",
        )
        assert card.name == "probe-agent"
        assert card.provider is not None
        assert card.provider["organization"] == "Covia"
        assert card.preferredTransport == "JSONRPC"

    def test_defaults(self):
        card = AgentCard(name="agent")
        assert card.name == "agent"
        assert card.provider is None
        assert card.skills is None

    def test_extra_fields_preserved(self):
        # Forward-compat: spec fields the model doesn't declare survive.
        card = AgentCard.model_validate({"name": "a", "securitySchemes": {"apiKey": {}}})
        assert card.model_dump()["securitySchemes"] == {"apiKey": {}}
