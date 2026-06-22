# Changelog

## Unreleased

### Added

- **`Venue.wait_until_ready()`** — block until the venue's API is ready to
  serve operations, polling `GET /api/v1/status` (not the root URL, which a
  venue answers before its invoke layer is initialised). Returns the ready
  `VenueStatus`, or raises `CoviaTimeoutError` if the venue is not ready
  within `timeout` (default 60s). Connection, HTTP, and per-request timeout
  errors are treated as "not ready yet" and retried. Mirrored on `AsyncVenue`.
- **`VenueStatus.status`** — the venue's readiness status field (e.g. `"OK"`)
  is now typed rather than only available via `extra`.
- **`UCANIssueResult`** — `venue.ucan.issue(...)` now returns a typed result
  (with a `token` attribute) instead of a raw dict, consistent with the other
  managers.
- **`AsyncAsset`** (`covia.async_api.AsyncAsset`) — `AsyncVenue.get_asset()`
  and `register()` now return an async-aware asset whose I/O methods
  (`get_content`, `put_content`, `invoke` → `AsyncJob`, `run`, `did_url`) are
  awaitable. Previously they returned the sync `Asset`, whose methods returned
  un-awaited coroutines (and `did_url` raised) on an `AsyncVenue`. Data
  accessors (`name`, `metadata`, `is_operation`, …) remain sync, shared with
  `Asset`.

### Changed

- **`venue.ucan.issue(...)` return type** — now returns `UCANIssueResult`
  rather than a raw dict. Migrate `result["token"]` → `result.token`.
- **Version single-sourced** in `src/covia/__init__.py`; `pyproject.toml`
  derives it via `[tool.hatch.version]`, so the package metadata and
  `covia.__version__` can no longer drift apart.

### Fixed

- **Async `Job.wait(timeout=...)`** now measures elapsed time with a
  wall-clock (`time.monotonic`) like the sync version, instead of summing the
  poll delays (which ignored network time and under-counted the timeout).
- **README** — corrected the asset example (`venue.register(...)` returns an
  `Asset`; there is no `venue.register_asset`), documented the `auth=`
  providers (`BearerAuth` / `BasicAuth` / `Ed25519Auth`) and the
  `agents` / `secrets` / `workspace` / `ucan` managers, and fixed the PyPI
  `Documentation` URL.

## 0.2.0 — 2026-06-11

### Added

- **UCAN proofs on invoke/run** — `venue.invoke(...)` and `venue.run(...)`
  now accept an optional `ucans=[token, ...]` keyword argument. The SDK
  forwards the tokens as the top-level `ucans` field in the
  ``/api/v1/invoke`` request envelope, allowing the venue to authorise
  capability-gated operations such as cross-DID lattice reads and
  `secret:extract`. Mirrored on `AsyncVenue`.
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
- Development Status remains `Alpha` (pre-1.0); the API surface may still change between minor versions.

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
