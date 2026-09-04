# Changelog

## 0.9.8

Targets Covia venue 0.9.8.

### Added

- Agent request options for the 0.9.8 schema: millisecond wire-level
  `timeout`, `sessionId`, `responseSchema`, `strict`, `outputPath`, and
  `loads`. Python timeout arguments remain seconds; the legacy `wait` keyword
  is retained as a compatibility alias.
- Complete saved-session management for agents: list, read, rename, compact,
  context reload, and delete, with typed result models and sync/async APIs.
- Typed `address` and `answered` agent response fields, status
  `version`/`ucanProfile`/`access` fields, and operation
  `activityLabel`/`readOnly`/`internal` metadata.
- Optional cancellation reasons for jobs and agent tasks.
- Per-call private execution with `venue.run(..., private=True)`.

### Changed

- `venue.run()` now uses Covia's result-oriented `POST /api/v1/run` endpoint
  directly. Its `timeout` controls the HTTP request; `invoke()` remains the
  Job-handle API.
- `venue.secrets.set()` sends `overwrite=False` by default, matching 0.9.8's
  protection against accidental replacement. Pass `overwrite=True` to replace
  an existing secret.
- `list_jobs()` follows every page instead of returning only the first 1,000
  job ids.
- A missing individual agent no longer disables the job-free agent GET
  transport for the rest of the connection.
- Agent chat supports concurrent calls on one session and exposes the message
  ids answered by each response.
- Agent creation follows the immutable-name 0.9.8 contract: pass a definition
  or layered config, and explicitly delete then create when replacing an
  existing agent.

## 0.9.0

Targets Covia venue 0.9.0. This release intentionally mirrors the published
`ai.covia:covia-core` 0.9.0 version line; there are no runtime changes from
Python SDK 0.7.0.

### Changed

- Align the Python package version with `covia-core` so the Java and Python
  client SDKs use the same release number. The Convex UCAN JWT profile support
  required by venue 0.9.0 (`ucv`, always-present `prf`, nullable `exp`) remains
  unchanged from 0.7.0.

## 0.7.0

Targets Covia venue 0.9.0.

### Changed

- **UCAN minting emits the Convex UCAN JWT profile** — `ucv` claim and
  always-present `prf`; `exp` is always present and may be `None` for a
  non-expiring token. Required by venues on Convex 0.8.11+ (#5)

## 0.6.0

Targets Covia venue 0.6.0.

### Fixed

- **`list_jobs()` accepts the 0.6.0 paged envelope** — venue 0.6.0 serves
  `GET /api/v1/jobs` as `{items, total, offset, limit}` (covia #229) instead of
  a flat id array; both the sync and async clients now handle either shape.

Every other 0.6.0 surface is already covered: `AgentListResult` matches the
enriched agent listings (#233), `stats` carries the new `jobs`/`userJobs`
counts, and skills are ordinary assets read through `get_asset()` — no special
handling.

## 0.5.0

Targets Covia venue 0.5.0.

### Added

- `AgentCreateResult.updated` and `AgentCreateResult.warnings` — typed fields
  for the venue 0.5 create advisories (non-tool-capable model, unresolvable
  tools) and the 0.4 in-place-update flag.

## 0.4.0

Targets Covia venue 0.4.0.

### Added

- **Job-free agent reads** — `venue.agents.list()` / `info()` now use the
  job-free `GET /api/v1/agents` transport (covia #180) on venues that support
  it, probing once per connection and falling back to the invoke path on
  older venues. No job record is minted for a read.
- **429 backpressure handling** — venue rate limits and concurrent-job caps
  (covia 0.4.0) are handled transparently: requests denied with 429 are
  retried with full-jitter exponential backoff honouring `Retry-After`
  (bounded — 4 attempts, 30s budget), after which a typed
  `RateLimitError` (carrying `retry_after`) is raised.
- **Private jobs (covia #192)** — `venue.set_private(True)` puts the
  connection in private-jobs mode: every `run()` executes as a memory-only
  job (never persisted, gone on venue restart; venue must enable
  `enablePrivateJobs`). Results are collected through the server-side
  invoke `wait` window; poll-style `invoke()` raises under private mode,
  since a completed private job is immediately forgotten. Sync + async.
- **Client-side UCAN minting** (`covia.ucan_tokens`, requires the
  `signing` extra) — mint tokens locally with your own Ed25519 key, no
  venue round-trip: `grant()` (self-sovereign delegation over your own
  namespace), `identity_token()` (empty-attenuation token proving control
  of a DID to a venue), `relay_delegation()` (venue/relay forwarding
  authority for cross-venue calls), plus `create_ucan_jwt()` / `did_for()`
  primitives.
- **`venue.ucan.verify(token, ...)`** — run the `ucan:verify` diagnostic
  against the venue's trust policy, returning a typed `UCANVerifyResult`
  (`valid`/`reason`, `chain_depth`, `root_issuer`, per-capability
  `rootAuthority` verdicts, and an optional would-it-authorise check via
  `with_`/`can`/`aud`).
- **`invoke(..., private=, wait=)`** — the low-level clients pass through
  the invoke body's `private` and `wait` fields (`wait=True` blocks up to
  the venue's cap; an int is milliseconds).

## 0.3.0

### Added

- **`venue.agent(id)` handle + `ChatSession`** — `venue.agent("a")` returns a
  lightweight `Agent` bound to one id that delegates to `venue.agents`, so
  `venue.agent("a").info()` reads the same as `venue.agents.info("a")`.
  `Agent.chat_session()` returns a `ChatSession` that auto-captures the
  server-minted session id across turns. Full sync + async parity
  (`AsyncAgent`, `AsyncChatSession`), matching the TS SDK's `Agent` handle.
- **Agent op parity** — `venue.agents` gained `fork`, `context`,
  `complete_task`, and `fail_task` (mirroring `v/ops/agent/*`), with typed
  `AgentForkResult` / `AgentCompleteTaskResult` / `AgentFailTaskResult`.
- **`venue.pin_asset(path)`** — pin any resolvable value into the caller's
  content-addressed asset store via `v/ops/asset/pin` (idempotent), returning
  a typed `AssetPinResult` (`path` / `hash`). Matches the TS `assets.pin`.
  Async mirror included.
- **`Job` interactive controls** — `Job.pause()` / `Job.resume()` (`PUT
  /jobs/{id}/pause|resume`) and `Job.send_message(message)` (`POST
  /jobs/{id}`, for delivering input to a paused/interactive job), plus
  `Job.needs_input` / `Job.needs_auth` predicates for the `INPUT_REQUIRED` /
  `AUTH_REQUIRED` states. Also exposed at the venue level (`venue.pause_job`
  / `resume_job` / `send_job_message`). Sync + async.
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
- **`ucans=` on the typed managers** — `venue.workspace.read/write/delete/append/list/slice`
  and `venue.secrets.extract` now accept a `ucans=[token]` argument, threaded
  into the invoke envelope. Previously capability-gated cross-DID access (reading
  another user's workspace, extracting a granted secret) could only be done by
  dropping to a raw `venue.run(op, input, ucans=[...])`; the ergonomic API now
  supports it directly. Mirrored on the async managers.
- **`venue.workspace.copy(from_path, to)`** — server-side value duplication via
  `v/ops/covia/copy`: reads any resolvable address and writes it to a writable
  path (`/w/`, `/o/`, `/n/`, `/t/`), returning a typed `WorkspaceCopyResult`
  (`existed` / `pathCreated`). Pin a venue op under your own `/o/`, cache remote
  data, or branch a workspace value. Matches the TS SDK's `workspace.copy`;
  async mirror included.
- **`covia.did` helpers** — `did_url(did, namespace, *segments)` and
  `parse_did_url` for building/splitting lattice addresses
  (`<DID>/<namespace>/<path>`), `is_did` / `did_method`, `did_web_to_url` /
  `url_to_did_web` (spec-correct, now with port `%3A` and path support), and
  `Namespace` constants. `Asset.did_url` and connection resolution route
  through these (no more duplicated string-building), and `resolve_connection`
  now handles ported/path `did:web` DIDs. The module documents which DID a
  lattice address takes: `w`/`o`/`g`/`j`/`s` are owner-DID-scoped (your auth
  DID), **not** the venue DID; only `a` (content-addressed assets) uses the
  venue DID.
- **`AsyncAsset`** (`covia.async_api.AsyncAsset`) — `AsyncVenue.get_asset()`
  and `register()` now return an async-aware asset whose I/O methods
  (`get_content`, `put_content`, `invoke` → `AsyncJob`, `run`, `did_url`) are
  awaitable. Previously they returned the sync `Asset`, whose methods returned
  un-awaited coroutines (and `did_url` raised) on an `AsyncVenue`. Data
  accessors (`name`, `metadata`, `is_operation`, …) remain sync, shared with
  `Asset`.

### Changed

- **`venue.agents.query()` renamed to `info()`.** Returns a typed
  `AgentInfoResult` — the venue's lightweight `{agentId, status, config?,
  stateConfig?, timelineLength?, tasks?}` summary — in place of the old
  straddle model that no longer matched the wire. **Breaking:** migrate
  `venue.agents.query(id)` → `venue.agents.info(id)`.
- **`AgentCard` model corrected to the A2A v1.0 wire shape.** The old fields
  (`agentProvider`, `agentCapabilities`, `agentSkills`, `agentInterfaces`,
  `securityScheme`) never matched what the venue serves at
  `/.well-known/agent-card.json` — they were always `None`. Now: `name`,
  `description`, `version`, `provider`, `capabilities`, `defaultInputModes`,
  `defaultOutputModes`, `skills`, `supportedInterfaces`, `preferredTransport`
  (a string). Verified against a live venue card. **Breaking** for anyone
  reading the old field names.
- **`AgentRequestResult.id` / `.status` are now optional.** A synchronously
  awaited request whose agent returns a bare result carries no id/status
  envelope; the model tolerates both shapes.
- **`venue.secrets.put()` removed — use `venue.secrets.set()`.** The two did
  the identical thing: the venue's REST `PUT /secrets/{name}` is just a thin
  wrapper over the `v/ops/secret/set` op that `set` already calls. The SDK now
  exposes a single store verb, and `set` returns a typed `SecretSetResult`
  (`put` discarded the result and returned `None`). The raw `venue.put_secret()`
  helper is removed too; `venue.list_secrets()` / `venue.delete_secret()`
  remain. **Breaking:** migrate `venue.secrets.put(n, v)` →
  `venue.secrets.set(n, v)`.
- **Result models target the 0.3.0 venue only.** Dropped the pre-0.3.0 straddle
  fields the 0.3.0 venue no longer sends: `WorkspaceReadResult.size`,
  `WorkspaceWriteResult.written`, `WorkspaceAppendResult.appended`, and
  `totalSize` on list/slice (use `count`). `WorkspaceListResult.values` is gone
  too — `list` returns `keys` (page elements with `slice`).
  `WorkspaceInspectResult.result` is now typed `str | dict[str, str]`, and
  `WorkspaceAggregateResult.groups` is `dict[str, GroupCount]` (was untyped) —
  access `result.groups[key].count`.
- **`venue.get_asset(ref)` accepts a lattice address.** As well as a content
  hash, `ref` may be `a/<hash>`, `<DID>/a/<hash>`, or a mutable lattice path
  the venue resolves to an asset (`w/my-assets/foo`, `o/my-op`, `<DID>/w/...`)
  — sent as a plain REST GET (not an operation). The hash-integrity check
  applies only to content-addressed refs; for a path the resolved canonical
  hash becomes the asset id. Sync and async share a `resolve_asset_id` helper,
  and `covia.did.asset_hash(ref)` exposes the content-hash detection. (Path
  resolution requires venue support — covia#150.)
- **Auth audience is now the venue's reported DID.** `Ed25519Auth` (when no
  audience is pinned) gets its JWT `aud` from the venue's reported `did` in
  `GET /api/v1/status` (falling back to `/.well-known/did.json`), resolved
  once per connection and cached — instead of `Grid.connect` deriving it from
  the connection string and mutating the auth object in place. Reusing the
  `status` response the client already needs for setup avoids an extra
  round-trip. This makes `aud` correct however you address the venue (URL or
  DID), and lets one `Ed25519Auth` be reused across venues safely. Pin
  `Ed25519Auth(audience=...)` to override. **Breaking:** `Auth.apply()` now
  takes an optional `audience` argument (`apply(self, headers, audience=None)`)
  and gains a `wants_audience` property — custom `Auth` subclasses must accept
  the new parameter.
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

### Removed

- **`InvokeRequest` model** — nothing constructed or consumed it (the client
  builds the invoke body inline). Dropped from the public exports.
- **`get_asset_did_document`** — dead client method (assets are
  content-addressed, not DID-document-resolved).
- **`JobData.message` field** — never read; `extra="allow"` still preserves
  it on the wire if a venue sends one.

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
