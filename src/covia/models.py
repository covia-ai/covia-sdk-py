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
#
# Response-model field names mirror the wire JSON verbatim (camelCase) — the
# same spelling the REST API, the raw payload, and the TypeScript SDK use, so
# there is one name per concept across the whole ecosystem. (Method *arguments*
# are snake_case Python kwargs the managers translate; only the response surface
# follows the wire.) ``extra="allow"`` keeps unmodelled fields accessible under
# their wire names too, so the convention holds for the long tail.


class VenueStatus(BaseModel):
    """Venue status returned by ``GET /api/v1/status``."""

    status: str | None = None
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
    """A2A agent card from ``GET /.well-known/agent-card.json``.

    Field names mirror the A2A v1.0 wire format the venue serves (via the
    official A2A Java SDK). ``extra="allow"`` preserves any spec fields a
    given venue build adds (e.g. ``securitySchemes``, ``protocolVersion``).
    """

    name: str
    description: str | None = None
    version: str | None = None
    provider: dict[str, Any] | None = None
    capabilities: dict[str, Any] | None = None
    defaultInputModes: list[str] | None = None
    defaultOutputModes: list[str] | None = None
    skills: list[dict[str, Any]] | None = None
    supportedInterfaces: list[dict[str, Any]] | None = None
    preferredTransport: str | None = None

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


class AgentInfoResult(BaseModel):
    """Result of ``v/ops/agent/info`` — a lightweight agent summary.

    Full state / history / timeline are read separately via ``covia:read`` on
    ``g/<agentId>/state`` etc. ``tasks`` is a *count*; ``stateConfig`` is only
    populated by legacy definition-created agents.
    """

    agentId: str
    status: str
    config: dict[str, Any] | None = None
    stateConfig: dict[str, Any] | None = None
    timelineLength: int | None = None
    tasks: int | None = None
    error: str | None = None

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


class AgentForkResult(BaseModel):
    """Result of ``v/ops/agent/fork``."""

    agentId: str
    status: str
    created: bool
    forkedFrom: str

    model_config = {"extra": "allow"}


class AgentCompleteTaskResult(BaseModel):
    """Result of ``v/ops/agent/complete-task``."""

    agentId: str
    taskId: str
    status: str

    model_config = {"extra": "allow"}


class AgentFailTaskResult(BaseModel):
    """Result of ``v/ops/agent/fail-task``."""

    agentId: str
    taskId: str
    status: str

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Workspace models (v/ops/covia/*)
# ---------------------------------------------------------------------------


# Result models target the 0.3.0 venue response shapes. Fields the venue only
# sometimes returns (e.g. ``pathCreated``, ``truncated``) are optional, and
# ``extra="allow"`` tolerates any additional/future fields under their wire
# names. The pre-0.3.0 straddle fields (``size``/``written``/``appended``/
# ``totalSize``) were dropped when the SDK adopted a 0.3.0-only floor.


class WorkspaceReadResult(BaseModel):
    """Result of ``v/ops/covia/read``.

    0.3.0: ``exists`` reflects path *presence* — a stored null reads back as
    ``exists=True, value=None`` (distinct from an absent path, ``exists=False``).
    """

    exists: bool
    value: Any = None
    truncated: bool | None = None
    type: str | None = None  # 0.3.0: Convex type name; included on a truncated read
    valueBytes: int | None = None  # 0.3.0: encoded size in bytes (always present)

    model_config = {"extra": "allow"}


class WorkspaceWriteResult(BaseModel):
    """Result of ``v/ops/covia/write``.

    Success is the job reaching ``COMPLETE`` (the SDK raises otherwise). 0.3.0
    (#147) returns ``existed`` (was there already a value at the path — created
    vs replaced); ``pathCreated`` is added only when a missing parent path was built.
    """

    existed: bool | None = None  # 0.3.0 (#147): False = created, True = replaced
    pathCreated: bool | None = None  # 0.3.0: true iff a new parent path was built

    model_config = {"extra": "allow"}


class WorkspaceCopyResult(BaseModel):
    """Result of ``v/ops/covia/copy`` — server-side value duplication.

    Copy reads the value at the source and writes it to the destination, so its
    outcome mirrors :class:`WorkspaceWriteResult` (the destination write's result).
    """

    existed: bool | None = None  # 0.3.0 (#147): False = created, True = replaced at destination
    pathCreated: bool | None = None  # 0.3.0: true iff a missing destination parent path was built

    model_config = {"extra": "allow"}


class WorkspaceDeleteResult(BaseModel):
    """Result of ``v/ops/covia/delete``.

    0.3.0 (#147): ``deleted`` is True if a value was present and removed, False for
    an idempotent no-op. (Pre-0.3.0: a constant True, then an empty object.)
    """

    deleted: bool | None = None  # 0.3.0 (#147): True = removed, False = no-op

    model_config = {"extra": "allow"}


class WorkspaceAppendResult(BaseModel):
    """Result of ``v/ops/covia/append``."""

    existed: bool | None = None  # 0.3.0 (#147): False = created, True = extended
    index: int | None = None  # 0.3.0 (#147): position the element landed (newSize-1)
    newSize: int | None = None  # 0.3.0: vector element count after the append
    pathCreated: bool | None = None  # 0.3.0: true iff a new parent path was built

    model_config = {"extra": "allow"}


class WorkspaceListResult(BaseModel):
    """Result of ``v/ops/covia/list`` — the direct children of a node.

    A map lists its ``keys``; sets and vectors report only ``type`` + ``count``
    (page their elements with :class:`WorkspaceSliceResult`).
    """

    exists: bool
    type: str
    count: int | None = None  # total entries (the single cardinality word)
    offset: int | None = None
    keys: list[str] | None = None  # populated for maps; None for sets/vectors/scalars

    model_config = {"extra": "allow"}


class WorkspaceSliceResult(BaseModel):
    """Result of ``v/ops/covia/slice``."""

    exists: bool
    type: str | None = None
    values: list[Any] | None = None
    count: int | None = None  # total entries (the single cardinality word)
    offset: int | None = None

    model_config = {"extra": "allow"}


class WorkspaceInspectResult(BaseModel):
    """Result of ``covia:inspect`` — a budget-bounded JSON5 render.

    ``result`` is a rendered string for a single path, or a ``{path: string}``
    map when multiple paths were inspected.
    """

    result: str | dict[str, str] | None = None

    model_config = {"extra": "allow"}


class WorkspaceCountResult(BaseModel):
    """Job-free tally (#177). ``exists`` = a countable collection is present at the
    path (an absent path or a scalar → ``exists=False``, no ``count``; an empty or
    too-deep collection → ``exists=True, count=0``)."""

    exists: bool
    count: int | None = None

    model_config = {"extra": "allow"}


class GroupCount(BaseModel):
    """One group's metrics in :attr:`WorkspaceAggregateResult.groups`.

    ``count`` today; numeric reductions (``sum``/``min``/``max``) will add keys
    additively, hence ``extra="allow"``.
    """

    count: int | None = None

    model_config = {"extra": "allow"}


class WorkspaceAggregateResult(BaseModel):
    """Job-free grouped tally (#177)."""

    exists: bool
    count: int | None = None
    # Present when ``group_by`` was supplied: each distinct field value → a
    # :class:`GroupCount`. An entry lacking the field groups under the ``"null"``
    # key. Σ(group counts) == count.
    groups: dict[str, GroupCount] | None = None

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# UCAN models (v/ops/ucan/*)
# ---------------------------------------------------------------------------


class UCANAttenuation(BaseModel):
    """A single capability grant in a UCAN ``att`` array."""

    with_: str = Field(alias="with")
    can: str

    model_config = {"extra": "allow", "populate_by_name": True}


class UCANIssueResult(BaseModel):
    """Result of ``v/ops/ucan/issue`` — the issued delegation token.

    Pass :attr:`token` as an element of the ``ucans`` list on subsequent
    invokes (``venue.run(op, input, ucans=[result.token])``).
    """

    token: str

    model_config = {"extra": "allow"}


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
