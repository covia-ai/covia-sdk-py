# Claude Code Guidelines for covia-sdk-py

## Project Overview

**covia-sdk-py** is the Python SDK for the [Covia](https://covia.ai) federated AI orchestration grid. It provides sync and async clients for connecting to Covia venues, invoking operations, managing assets, and tracking job lifecycle — all with full type safety.

- **Package name:** `covia`
- **Version:** 0.2.0
- **License:** Apache-2.0
- **Python:** 3.11+
- **Build system:** Hatchling (PEP 517)
- **Repository:** https://github.com/covia-ai/covia-sdk-py

---

## Quick Reference

```bash
# Install for development
pip install -e ".[dev]"

# Run unit tests
pytest tests/unit -v

# Run unit tests with coverage
pytest tests/unit --cov=covia --cov-report=term

# Run integration tests (requires live venue)
COVIA_VENUE_URL=https://venue-3.covia.ai pytest -m integration

# Lint
ruff check src/ tests/

# Format check / auto-format
ruff format --check src/ tests/
ruff format src/ tests/

# Type check
mypy src/covia/
```

---

## Module Structure

```
src/covia/
  __init__.py          # Public API exports and __version__
  grid.py              # Grid.connect() — entry point for venue connections
  venue.py             # Venue — primary class; holds lazy managers
  job.py               # Job — job lifecycle, polling, SSE streaming
  asset.py             # Asset — data objects and invocable operations
  status.py            # JobStatus enum (PENDING, STARTED, COMPLETE, etc.)
  models.py            # Pydantic v2 data models for API types
  exceptions.py        # Exception hierarchy (CoviaError base)
  auth.py              # Auth interface + built-in providers
  agents.py            # AgentManager / AsyncAgentManager — v/ops/agent/*
  secrets.py           # SecretManager / AsyncSecretManager
  workspace.py         # WorkspaceManager / AsyncWorkspaceManager — v/ops/covia/*
  ucan.py              # UCANManager / AsyncUCANManager — v/ops/ucan/*
  _client.py           # Synchronous HTTP client (internal)
  _async_client.py     # Asynchronous HTTP client (internal)
  _transport.py        # Transport config, URL/DID resolution (internal)
  _sse.py              # SSE event dataclass (internal)
  py.typed             # PEP 561 marker
  async_api/           # Full async API mirror
    __init__.py
    grid.py            # AsyncGrid
    venue.py           # AsyncVenue
    job.py             # AsyncJob
```

### Public API

**Core classes:** `Grid`, `Venue`, `Job`, `Asset`, `JobStatus`

**Managers (lazy properties on Venue):** `venue.agents`, `venue.secrets`, `venue.workspace`, `venue.ucan`

**Models:** `VenueStatus`, `AssetList`, `AssetPinResult`, `JobData`, `DIDDocument`, `MCPDiscovery`, `AgentCard`, `OperationInfo`, plus agent/workspace/ucan/secret result models (see `covia/__init__.py`).

**Exceptions:** `CoviaError`, `GridError`, `CoviaConnectionError`, `CoviaTimeoutError`, `JobFailedError`, `AssetNotFoundError`, `JobNotFoundError`

**Async variants:** `covia.async_api.AsyncGrid`, `AsyncVenue`, `AsyncJob`, plus `AsyncAgentManager`, `AsyncSecretManager`, `AsyncWorkspaceManager`, `AsyncUCANManager`

### Manager wiring

Managers are lazy properties on `Venue` / `AsyncVenue` — first access constructs, subsequent accesses return the cached instance. Each manager delegates to the venue via:

- `venue.run(op, input)` — for ops that go through `/api/v1/invoke` (agent, workspace, ucan, secret set/extract)
- `venue.list_secrets()` / `delete_secret()` — for the REST secret endpoints (storing goes through `venue.secrets.set`)

Payloads sent on the wire are camelCase to match the Covia REST API; Python args are snake_case and managers handle the translation.

---

## Dependencies

### Runtime
- **httpx** >= 0.27, < 1.0 — HTTP client (sync + async)
- **pydantic** >= 2.0, < 3.0 — Data validation and serialization
- **httpx-sse** >= 0.4, < 1.0 — Server-sent events support

### Dev
- **pytest** >= 8.0 — Test framework
- **pytest-asyncio** >= 0.24 — Async test support (`asyncio_mode = "auto"`)
- **pytest-httpx** >= 0.34 — HTTP request mocking
- **pytest-cov** >= 5.0 — Coverage reporting
- **ruff** >= 0.8 — Linter and formatter
- **mypy** >= 1.13 — Static type checker (strict mode, pydantic plugin)

---

## Testing

Tests live in `tests/` with shared fixtures in `conftest.py`.

| Directory | Count | Description |
|-----------|-------|-------------|
| `tests/unit/` | 120+ | Mocked HTTP via pytest-httpx, covers all classes and managers |
| `tests/integration/` | — | Requires live venue, marked `@pytest.mark.integration` |

Unit tests are the primary quality gate. Always run them after changes:

```bash
pytest tests/unit -v
```

Integration tests are excluded by default. Run explicitly with `-m integration` and a `COVIA_VENUE_URL` env var.

---

## Code Conventions

### Style
- **Formatter/Linter:** Ruff (line length 120, target Python 3.11)
- **Lint rules:** E, F, I (isort), UP (pyupgrade), B (bugbear), SIM (simplify)
- **Type checking:** mypy strict mode with pydantic plugin
- **PEP 561:** Fully typed (`py.typed` marker included)

### Patterns
- `from __future__ import annotations` in all modules
- `TYPE_CHECKING` guards for circular/forward imports
- Private modules prefixed with `_` (e.g. `_client.py`, `_transport.py`)
- Pydantic v2 models with `extra="allow"` for forward compatibility
- Context managers for connection lifecycle (`with Grid.connect(...) as venue:`)
- Exponential backoff polling (0.3s initial, 1.5x factor, 10s max)
- Sync and async APIs kept in parallel with matching interfaces

### Naming
- Package: `covia`
- Public classes: PascalCase (`Grid`, `Venue`, `Job`, `Asset`)
- Private modules: underscore-prefixed (`_client`, `_transport`, `_sse`)
- Test files mirror source: `test_grid.py`, `test_venue.py`, etc.

---

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on push/PR to `master`:

1. **Matrix:** Python 3.11, 3.12, 3.13 on Ubuntu
2. **Lint:** `ruff check`
3. **Format:** `ruff format --check`
4. **Type check:** `mypy src/covia/`
5. **Unit tests:** `pytest tests/unit` with coverage
6. **Coverage upload:** Codecov on Python 3.12

---

## Branch Strategy

- **`master`** — Primary branch; **always reflects the latest published release**. Every commit on `master` should correspond to a released (tagged) state.
- **`develop`** — Active development; may be ahead of `master` between releases.
- Feature branches and PRs as needed.

---

## Release process

Releases are tag-driven: pushing a `vX.Y.Z` tag triggers `publish.yml` (CI → build → PyPI → GitHub Release). The publish job's `validate-tag` step requires the tag (minus the `v`) to equal `version` in `pyproject.toml` **exactly**.

Checklist:

1. On `develop`, bump `__version__` in `src/covia/__init__.py` (the single
   version source — `pyproject.toml` reads it via `[tool.hatch.version]`) and
   update `CHANGELOG.md`.
2. Commit (e.g. `Release X.Y.Z`) and push `develop`.
3. Tag the release commit and push the tag — this triggers `publish.yml`:
   ```bash
   git tag vX.Y.Z && git push origin vX.Y.Z
   ```
4. **Promote `master` to the release** so it reflects the latest release:
   ```bash
   git checkout master
   git merge --ff-only vX.Y.Z      # master fast-forwards to the tagged commit
   git push origin master
   git checkout develop
   ```
5. Confirm the **Release branch guard** workflow (`release-guard.yml`) is green.

> Step 4 is the easy one to forget — skipping it leaves `master` stale (this is exactly how `master` once drifted behind `v0.2.0`). The guard workflow fails if `master` doesn't contain the latest final-release tag.

### Tag format

- Tags use the **`v` prefix** (`v0.2.0`) — the standard Git convention. The `v` is **not** part of the package version; PyPI tooling and `validate-tag` strip it.
- The remainder is a [PEP 440](https://peps.python.org/pep-0440/) version and must match `pyproject.toml` exactly (normalised form). Use PEP 440 spellings, **not** SemVer-style suffixes:
  - Pre-release: `v0.3.0a1`, `v0.3.0b1`, `v0.3.0rc1` &nbsp;(not `v0.3.0-alpha.1`)
  - Post / dev: `v0.3.0.post1`, `v0.3.0.dev1`

---

## Development Workflow

1. **Read existing code** before proposing changes
2. **Run the full check suite** after changes:
   ```bash
   ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/covia/ && pytest tests/unit -v
   ```
3. **Follow existing patterns** — sync/async parity, Pydantic models, httpx client structure
4. **Prefer editing existing files** over creating new ones
5. **Keep the public API surface minimal** — export only via `__init__.py` `__all__`

---

## Key Resources

- **Covia Docs:** https://docs.covia.ai
- **SDK Docs:** https://docs.covia.ai/docs/user-guide/sdk/python — lives in [covia-docs](https://github.com/covia-ai/covia-docs) repo at `docs/user-guide/sdk/python.md`
- **Covia Discord:** https://discord.gg/fywdrKd8QT
- **GitHub:** https://github.com/covia-ai/covia-sdk-py
