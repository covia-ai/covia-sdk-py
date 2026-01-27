# Claude Code Guidelines for covia-sdk-py

## Project Overview

**covia-sdk-py** is the Python SDK for the [Covia](https://covia.ai) federated AI orchestration grid. It provides sync and async clients for connecting to Covia venues, invoking operations, managing assets, and tracking job lifecycle — all with full type safety.

- **Package name:** `covia`
- **Version:** 0.1.0 (Alpha)
- **License:** Apache-2.0
- **Python:** 3.10+
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
COVIA_VENUE_URL=https://venue-test.covia.ai pytest -m integration

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
  venue.py             # Venue — primary class for venue interaction
  job.py               # Job — job lifecycle, polling, SSE streaming
  asset.py             # Asset — data objects and invocable operations
  status.py            # JobStatus enum (PENDING, STARTED, COMPLETE, etc.)
  models.py            # Pydantic v2 data models for API types
  exceptions.py        # Exception hierarchy (CoviaError base)
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

**Models:** `VenueStatus`, `AssetList`, `JobData`, `DIDDocument`, `MCPDiscovery`, `AgentCard`, `InvokeRequest`

**Exceptions:** `CoviaError`, `CoviaAPIError`, `CoviaConnectionError`, `CoviaTimeoutError`, `JobFailedError`, `AssetNotFoundError`, `JobNotFoundError`

**Async variants:** `covia.async_api.AsyncGrid`, `AsyncVenue`, `AsyncJob`

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
| `tests/unit/` | 92 | Mocked HTTP via pytest-httpx, covers all classes |
| `tests/integration/` | — | Requires live venue, marked `@pytest.mark.integration` |

Unit tests are the primary quality gate. Always run them after changes:

```bash
pytest tests/unit -v
```

Integration tests are excluded by default. Run explicitly with `-m integration` and a `COVIA_VENUE_URL` env var.

---

## Code Conventions

### Style
- **Formatter/Linter:** Ruff (line length 120, target Python 3.10)
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

GitHub Actions (`.github/workflows/ci.yml`) runs on push/PR to `main`:

1. **Matrix:** Python 3.10, 3.11, 3.12, 3.13 on Ubuntu
2. **Lint:** `ruff check`
3. **Format:** `ruff format --check`
4. **Type check:** `mypy src/covia/`
5. **Unit tests:** `pytest tests/unit` with coverage
6. **Coverage upload:** Codecov on Python 3.12

---

## Branch Strategy

- **`master`** — Primary branch
- CI configured to trigger on `main` (align as needed)
- Feature branches and PRs as needed

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
- **SDK Docs:** https://docs.covia.ai/sdk/python
- **Covia Discord:** https://discord.gg/fywdrKd8QT
- **GitHub:** https://github.com/covia-ai/covia-sdk-py
