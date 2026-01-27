"""Pydantic v2 models for Covia API requests and responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from covia.status import JobStatus

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class InvokeRequest(BaseModel):
    """Request body for ``POST /api/v1/invoke``."""

    operation: str
    input: Any = None


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class VenueStatus(BaseModel):
    """Venue status returned by ``GET /api/v1/status``."""

    url: str | None = None
    did: str | None = None
    name: str | None = None
    stats: dict[str, Any] | None = None

    model_config = {"extra": "allow"}


class AssetList(BaseModel):
    """Paginated asset list returned by ``GET /api/v1/assets``."""

    items: list[str]
    total: int
    offset: int
    limit: int


class JobData(BaseModel):
    """Job data returned by invoke and job status endpoints."""

    id: str | None = None
    status: JobStatus = JobStatus.PENDING
    output: Any = None
    error: str | None = None
    operation: str | None = None
    input: Any = None
    message: str | None = None

    model_config = {"extra": "allow"}


class ErrorResponse(BaseModel):
    """Standard error response body."""

    error: str
    data: Any = None


class DIDDocument(BaseModel):
    """DID document from ``GET /.well-known/did.json``."""

    id: str
    context: str | list[str] | None = Field(None, alias="@context")

    model_config = {"extra": "allow", "populate_by_name": True}


class MCPDiscovery(BaseModel):
    """MCP discovery info from ``GET /.well-known/mcp``."""

    mcp_version: str | None = None
    server_url: str | None = None
    description: str | None = None
    tools_endpoint: str | None = None
    endpoint: str | None = None

    model_config = {"extra": "allow"}


class AgentCard(BaseModel):
    """A2A agent card from ``GET /.well-known/agent-card.json``."""

    agentProvider: dict[str, Any] | None = None
    agentCapabilities: dict[str, Any] | None = None
    agentSkills: list[dict[str, Any]] | None = None
    agentInterfaces: list[dict[str, Any]] | None = None
    securityScheme: dict[str, Any] | None = None
    preferredTransport: dict[str, Any] | None = None

    model_config = {"extra": "allow"}
