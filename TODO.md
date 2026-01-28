# covia-sdk-py — Priority TODOs

## 1. ~~Caching~~ DONE

### 1a. ~~Cache Venue DID~~ DONE

`Venue.did` now fetches from `/.well-known/did.json` on first access and caches
the result. `AsyncVenue.get_did()` does the same. `did_document()` is unaffected
and always fetches fresh.

### 1b. ~~Cache asset metadata as raw UTF-8~~ DONE

`CoviaHTTPClient.get_asset_metadata()` now returns `tuple[dict, str]` — the
parsed dict and the raw UTF-8 response text. `Asset` stores both via a new
`metadata_raw` property. This preserves the exact server representation needed
for SHA-256 asset ID computation and validation.

---

## 2. ~~Authentication support~~ DONE (basic)

Generic `Auth` interface added (`covia.auth`). `Grid.connect()` and
`AsyncGrid.connect()` accept `auth=` parameter. Built-in providers:
`NoAuth`, `BearerAuth`, `BasicAuth`. Interface is extensible for future
OAuth 2.0 and Ed25519 signing providers.

## 3. ~~Specialized exceptions are never raised~~ DONE

Asset/job methods now raise `AssetNotFoundError` / `JobNotFoundError` on 404
via thin `_request_asset` / `_request_job` helpers in both clients. Non-404
errors still raise `GridError`. `CoviaConnectionError` and
`CoviaTimeoutError` now also subclass Python's built-in `ConnectionError` and
`TimeoutError` for idiomatic `except` usage.

## 4. ~~No logging~~ DONE

Added `logging` module integration across the SDK. `NullHandler` on the root
`covia` logger (silent by default). DEBUG-level tracing for HTTP requests/responses,
DID resolution, connection establishment, and job polling cycles. WARNING for
plain HTTP (non-TLS) connections. Library never configures handlers — users
opt-in via standard `logging.basicConfig()` or handler setup.

## 5. No retry/resilience on transient failures

A single transient HTTP error (5xx, connection reset) causes an immediate
exception. The polling loop in `job.py` retries on schedule, but `_client.py`
request methods have no retry logic. Add configurable retries for idempotent GET
requests and transient server errors.

## 6. Integration tests are skeletal

Only 3 tests in `test_venue_live.py` with trivial assertions
(`assert status is not None`). Missing coverage: invoke/run operations, job
lifecycle (wait, cancel), asset content upload/download, SSE streaming, error
paths, async API.

## 7. No PyPI release workflow

CI runs lint/test/typecheck but has no workflow for building and publishing to
PyPI. Set up a GitHub Actions workflow with `hatch build` and `hatch publish`
gated on tag/release events.

## 8. ~~Branch name mismatch~~ DONE

Aligned CI, CLAUDE.md, and pyproject.toml on `master` as the primary branch.

## 9. Sphinx documentation not built

`pyproject.toml` declares a `docs` optional-dependency extra with Sphinx, but no
`docs/` directory, `conf.py`, or Sphinx configuration exists. The infrastructure
is declared but not created.

## 10. SSE event handling is minimal

`_sse.py` is a 24-line dataclass with no event-type dispatch, no automatic JSON
parsing of `data` fields, and no reconnection logic on stream drop. At minimum,
parse JSON event data and handle stream disconnection gracefully.
