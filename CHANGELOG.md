# Changelog

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
