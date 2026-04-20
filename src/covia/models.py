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
    endpoint: dict[str, Any] | str | None = None

    model_config = {"extra": "allow"}


class OperationInfo(BaseModel):
    """Named operation info returned by ``GET /api/v1/operations``."""

    name: str
    asset: str
    description: str | None = None
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None

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


# ---------------------------------------------------------------------------
# Agent models (wire format: camelCase to match the v/ops/agent/* API)
# ---------------------------------------------------------------------------


class AgentCreateResult(BaseModel):
    """Result of ``v/ops/agent/create``."""

    agentId: str
    status: str
    created: bool

    model_config = {"extra": "allow"}


class AgentRequestResult(BaseModel):
    """Result of ``v/ops/agent/request``."""

    id: str
    status: str
    output: Any = None

    model_config = {"extra": "allow"}


class AgentMessageResult(BaseModel):
    """Result of ``v/ops/agent/message``."""

    agentId: str
    delivered: bool

    model_config = {"extra": "allow"}


class AgentChatResult(BaseModel):
    """Result of ``v/ops/agent/chat``.

    ``sessionId`` is minted by the server on the first call (when none is
    supplied). Capture it and pass on subsequent calls to continue the
    conversation on the same session.
    """

    agentId: str
    sessionId: str
    response: Any = None

    model_config = {"extra": "allow"}


class AgentTriggerResult(BaseModel):
    """Result of ``v/ops/agent/trigger``."""

    agentId: str
    status: str
    result: Any = None
    taskResults: list[Any] | None = None

    model_config = {"extra": "allow"}


class AgentQueryResult(BaseModel):
    """Result of ``v/ops/agent/info``."""

    agentId: str
    status: str
    state: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    tasks: list[Any] | None = None

    model_config = {"extra": "allow"}


class AgentListEntry(BaseModel):
    """Single entry in ``AgentListResult.agents``."""

    agentId: str
    status: str
    tasks: int

    model_config = {"extra": "allow"}


class AgentListResult(BaseModel):
    """Result of ``v/ops/agent/list``."""

    agents: list[AgentListEntry]

    model_config = {"extra": "allow"}


class AgentDeleteResult(BaseModel):
    """Result of ``v/ops/agent/delete``."""

    agentId: str
    status: str
    removed: bool | None = None

    model_config = {"extra": "allow"}


class AgentSuspendResult(BaseModel):
    """Result of ``v/ops/agent/suspend`` and ``v/ops/agent/resume``."""

    agentId: str
    status: str

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Workspace models (v/ops/covia/*)
# ---------------------------------------------------------------------------


class WorkspaceReadResult(BaseModel):
    """Result of ``v/ops/covia/read``."""

    exists: bool
    value: Any = None
    truncated: bool | None = None
    size: int | None = None

    model_config = {"extra": "allow"}


class WorkspaceWriteResult(BaseModel):
    """Result of ``v/ops/covia/write``."""

    written: bool

    model_config = {"extra": "allow"}


class WorkspaceDeleteResult(BaseModel):
    """Result of ``v/ops/covia/delete``."""

    deleted: bool

    model_config = {"extra": "allow"}


class WorkspaceAppendResult(BaseModel):
    """Result of ``v/ops/covia/append``."""

    appended: bool

    model_config = {"extra": "allow"}


class WorkspaceListResult(BaseModel):
    """Result of ``v/ops/covia/list``."""

    exists: bool
    type: str
    count: int | None = None
    keys: list[str] | None = None
    values: list[Any] | None = None

    model_config = {"extra": "allow"}


class WorkspaceSliceResult(BaseModel):
    """Result of ``v/ops/covia/slice``."""

    exists: bool
    type: str
    values: list[Any]
    count: int
    offset: int

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# UCAN models (v/ops/ucan/*)
# ---------------------------------------------------------------------------


class UCANAttenuation(BaseModel):
    """A single capability grant in a UCAN ``att`` array."""

    with_: str = Field(alias="with")
    can: str

    model_config = {"extra": "allow", "populate_by_name": True}


# ---------------------------------------------------------------------------
# Secret models (v/ops/secret/*)
# ---------------------------------------------------------------------------


class SecretSetResult(BaseModel):
    """Result of ``v/ops/secret/set``."""

    name: str
    stored: bool

    model_config = {"extra": "allow"}


class SecretExtractResult(BaseModel):
    """Result of ``v/ops/secret/extract``.

    NOTE: requires a UCAN capability grant; the venue may reject requests
    that lack the appropriate capability proof.
    """

    name: str
    value: str

    model_config = {"extra": "allow"}
