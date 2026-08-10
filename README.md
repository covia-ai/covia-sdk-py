# Covia Python SDK

Python SDK for the [Covia](https://covia.ai) federated AI orchestration grid.

Covia enables AI models, agents, and data to collaborate across organisational boundaries, clouds, and jurisdictions — with built-in governance and without centralising control.

## Installation

```bash
pip install covia
```

Python SDK release numbers mirror the published
[`ai.covia:covia-core`](https://central.sonatype.com/artifact/ai.covia/covia-core)
version line. Venue compatibility and any protocol migrations are recorded in
the [changelog](CHANGELOG.md).

## Quick Start

```python
from covia import Grid

# Connect to a venue
venue = Grid.connect("https://venue.covia.ai")

# Invoke an operation and get the result
result = venue.run("my-operation", {"prompt": "hello"})
print(result)
```

## Usage

### Connect to a Venue

```python
from covia import Grid

# By URL
venue = Grid.connect("https://venue.covia.ai")

# By DID
venue = Grid.connect("did:web:venue.covia.ai")

# With authentication (see "Authentication" below)
from covia.auth import BearerAuth
venue = Grid.connect("https://venue.covia.ai", auth=BearerAuth("<token>"))

# With extra custom headers
venue = Grid.connect("https://venue.covia.ai", headers={"X-Trace-Id": "abc"})

# As a context manager
with Grid.connect("https://venue.covia.ai") as venue:
    venue.wait_until_ready()   # optional: block until a cold venue is ready
    result = venue.run("my-operation", {"prompt": "hello"})
```

### Authentication

Pass an auth provider to `Grid.connect(..., auth=...)`:

```python
from covia import Grid
from covia.auth import BearerAuth, BasicAuth, Ed25519Auth

# Bearer token
venue = Grid.connect("https://venue.covia.ai", auth=BearerAuth("<token>"))

# HTTP Basic
venue = Grid.connect("https://venue.covia.ai", auth=BasicAuth("user", "pass"))

# Self-issued Ed25519 JWT (requires the signing extra: pip install covia[signing])
auth = Ed25519Auth.generate(audience="did:web:venue.covia.ai")
print(auth.did)  # did:key:z6Mk...
venue = Grid.connect("did:web:venue.covia.ai", auth=auth)
```

### Invoke Operations

```python
# Fire-and-forget with a Job handle
job = venue.invoke("my-operation", {"prompt": "hello"})
job.wait(timeout=60)
print(job.status)   # JobStatus.COMPLETE
print(job.output)   # The result

# Or use run() to invoke and wait in one call
result = venue.run("my-operation", {"prompt": "hello"}, timeout=30)

# Use result() on a Job
output = venue.invoke("my-op", {"x": 1}).result(timeout=30)
```

#### Private jobs

`venue.set_private(True)` puts the connection in **private-jobs mode**: every
subsequent `run()` executes as a memory-only job — never persisted to the
venue's job index, gone on venue restart (the venue must enable
`enablePrivateJobs`). Results are collected through the server-side invoke
`wait` window rather than polling, because a completed private job is
immediately forgotten — so private mode works with `run()`, and poll-style
`invoke()` raises.

```python
venue.set_private(True)
result = venue.run("v/ops/schema/infer", {"value": {"name": "Ada"}})
```

### Job Lifecycle

```python
from covia import JobStatus

job = venue.invoke("long-operation", {"data": "..."})

# Poll status
print(job.status)      # JobStatus.PENDING
job.refresh()
print(job.status)      # JobStatus.STARTED

# Wait for completion
job.wait(timeout=120)

# Check result
if job.is_complete:
    print(job.output)
elif job.error:
    print(f"Failed: {job.error}")

# Cancel a running job
job.cancel()

# Stream SSE updates
for event in job.stream():
    print(event.data)
```

### Asset Management

```python
# Register an asset — returns an Asset with a server-assigned id
asset = venue.register({
    "name": "Training Data",
    "description": "Model training dataset",
    "content-type": "application/json",
})
print(asset.id)

# Upload content
asset.put_content(b'{"records": [...]}')

# Retrieve an asset
asset = venue.get_asset(asset.id)
print(asset.name)
print(asset.metadata)

# Download content
data = asset.get_content()

# Invoke an operation asset directly
op = venue.get_asset("abc123...")
if op.is_operation:
    result = op.run({"x": 1})

# List assets
assets = venue.list_assets(limit=100)
print(f"{assets.total} assets available")
```

### Venue Discovery

```python
# Venue status
status = venue.status()

# DID document
did_doc = venue.did_document()

# MCP discovery
mcp = venue.mcp_discovery()

# A2A agent card
card = venue.agent_card()
```

### Agents, Secrets, Workspace & UCANs

Typed accessors for the venue's `v/ops/*` operations:

```python
# Agents (v/ops/agent/*)
venue.agents.create("my-agent", config={...}, overwrite=True)
reply = venue.agents.chat("my-agent", "hello")     # returns AgentChatResult
print(reply.sessionId, reply.response)

# Secrets (v/ops/secret/* and REST)
venue.secrets.set("ANTHROPIC_API_KEY", "sk-...")
print(venue.secrets.list())

# Workspace lattice (v/ops/covia/*)
venue.workspace.write("w/notes/today", {"text": "hi"})
print(venue.workspace.read("w/notes/today").value)

# UCAN delegation (v/ops/ucan/*)
from covia import UCANAttenuation
token = venue.ucan.issue(
    "did:key:zBob",
    [UCANAttenuation(with_="did:key:zAlice/w/shared", can="crud/read")],
    expiry=2_000_000_000,
).token
result = venue.run("v/ops/covia/read", {"path": "did:key:zAlice/w/shared"}, ucans=[token])

# Diagnose a token against the venue's trust policy
verdict = venue.ucan.verify(token, with_="did:key:zAlice/w/shared", can="crud/read", aud="did:key:zBob")
print(verdict.valid, verdict.root_issuer, verdict.authorises)
```

Tokens can also be minted **client-side** with your own Ed25519 key — no venue
round-trip (requires the `signing` extra: `pip install covia[signing]`):

```python
from covia.ucan_tokens import grant, identity_token, relay_delegation, did_for

# Self-sovereign grant over your own namespace — verifies on ANY venue
token = grant(private_key, "did:key:zBob", f"{did_for(private_key)}/w/shared/", "crud/read", 3600)

# Identity token — proves control of your DID to a venue (empty attenuation)
id_token = identity_token(private_key, venue_did)

# Relay delegation — authorises the venue to forward your authority cross-venue
relay = relay_delegation(private_key, venue_did, 300, [{"with": f"{did_for(private_key)}/w/", "can": "crud/read"}])
```

### Async Support

```python
from covia.async_api import AsyncGrid

async def main():
    async with AsyncGrid.connect("https://venue.covia.ai") as venue:
        # All methods are async
        status = await venue.status()
        result = await venue.run("my-operation", {"prompt": "hello"})

        # Async job lifecycle
        job = await venue.invoke("long-op", {"data": "..."})
        output = await job.result(timeout=60)

        # Async assets — get_asset/register return an AsyncAsset
        asset = await venue.get_asset("abc123...")
        if asset.is_operation:            # data accessors stay sync
            out = await asset.run({"x": 1})
        data = await asset.get_content()
```

### Error Handling

```python
from covia import Grid, CoviaError, GridError, JobFailedError, CoviaTimeoutError, RateLimitError

try:
    result = venue.run("might-fail", {"x": 1}, timeout=30)
except JobFailedError as e:
    print(f"Job failed: {e.job_data.error}")
except CoviaTimeoutError:
    print("Operation timed out")
except RateLimitError as e:
    # 429 after bounded automatic retries — rate limit or concurrent-job cap
    print(f"Rate limited, retry after {e.retry_after_seconds}s")
except GridError as e:
    print(f"API error {e.status_code}: {e.message}")
except CoviaError as e:
    print(f"SDK error: {e}")
```

## Development

```bash
# Clone and install
git clone https://github.com/covia-ai/covia-sdk-py.git
cd covia-sdk-py
pip install -e ".[dev]"

# Run tests
pytest tests/unit

# Lint and type check
ruff check src/ tests/
mypy src/covia/

# Integration tests (requires a live venue)
COVIA_VENUE_URL=https://venue-3.covia.ai pytest -m integration
```

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Links

- [Python SDK Documentation](https://docs.covia.ai/docs/user-guide/sdk/python)
- [Covia Documentation](https://docs.covia.ai)
- [Covia Website](https://covia.ai)
- [GitHub](https://github.com/covia-ai/covia-sdk-py)
- [Discord](https://discord.gg/fywdrKd8QT)
