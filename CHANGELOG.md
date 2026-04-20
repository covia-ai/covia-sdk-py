# Changelog

## 0.2.0a1

### Added

- **AgentManager** (`venue.agents`) — typed wrapper over the `v/ops/agent/*`
  operations: `create`, `request`, `message`, `chat`, `trigger`, `query`,
  `list`, `delete`, `suspend`, `resume`, `update`, `cancel_task`.
- **Session-based `chat()`** — `venue.agents.chat(agent_id, message, session_id=None)`
  blocks until the agent produces its next response on the session. Omit
  `session_id` on the first call — the server mints one and returns it in
  `AgentChatResult.sessionId`. Pass it back on subsequent calls to continue
  the conversation. Only one chat may be in flight per session.
- **SecretManager** (`venue.secrets`) — `list`, `put`, `delete` via raw REST
  plus `set` and `extract` via `v/ops/secret/*` (the latter requires a UCAN
  capability grant). Raw REST helpers also exposed as `venue.list_secrets()`,
  `venue.put_secret()`, `venue.delete_secret()`.
- **WorkspaceManager** (`venue.workspace`) — `read`, `write`, `delete`,
  `append`, `list`, `slice` over `v/ops/covia/*`.
- **UCANManager** (`venue.ucan`) — `issue(audience, attenuations, expiry)`
  for UCAN delegation via `v/ops/ucan/issue`.
- **Pydantic models** for every manager response and for `UCANAttenuation`
  (re-exported from the top-level `covia` package).
- **Async mirrors** — `AsyncAgentManager`, `AsyncSecretManager`,
  `AsyncWorkspaceManager`, `AsyncUCANManager`, accessible via the same
  property names on `AsyncVenue`.

### Changed

- Python minimum raised to **3.11** (from 3.10) — required by
  `enum.StrEnum`, used in `JobStatus`.
- Development Status still `Alpha`; API surface may change before 0.2.0 final.

## 0.1.0

Initial release of the Covia Python SDK.

- Grid entry point with URL and DID connection support
- Venue class for asset management, operation invocation, and job tracking
- Job lifecycle with polling, wait, cancel, and SSE streaming
- Asset class with metadata, content upload/download, and invocation
- Full async API via `covia.async_api`
- Pydantic v2 models for all request/response types
- MCP, A2A, and DID discovery endpoints
- Comprehensive exception hierarchy
- Type hints throughout (PEP 561 compatible)
