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
- **`ucans=` on the typed managers** — `venue.workspace.read/write/delete/append/list/slice`
  and `venue.secrets.extract` now accept a `ucans=[token]` argument, threaded
  into the invoke envelope. Previously capability-gated cross-DID access (reading
  another user's workspace, extracting a granted secret) could only be done by
  dropping to a raw `venue.run(op, input, ucans=[...])`; the ergonomic API now
  supports it directly. Mirrored on the async managers.
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
  audience is pinned) gets its JWT `aud` from the venue's DID document
  (`/.well-known/did.json`), resolved once per connection and cached — instead
  of `Grid.connect` deriving it from the connection string and mutating the
  auth object in place. This makes `aud` correct however you address the venue
  (URL or DID), and lets one `Ed25519Auth` be reused across venues safely.
  Pin `Ed25519Auth(audience=...)` to override. **Breaking:** `Auth.apply()`
  now takes an optional `audience` argument (`apply(self, headers, audience=None)`)
  and gains a `wants_audience` property — custom `Auth` subclasses must accept
  the new parameter. The first authenticated request now performs a one-time
  `did.json` fetch to resolve the audience.
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
