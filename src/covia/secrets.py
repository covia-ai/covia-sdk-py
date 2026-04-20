"""SecretManager — typed wrapper for venue-scoped secret storage.

The manager combines two REST endpoints (``/api/v1/secrets/*``) with two
capability-scoped operations (``v/ops/secret/set`` and
``v/ops/secret/extract``). Extraction requires a UCAN capability proof and
will be rejected without one.
"""

from __future__ import annotations

from typing import Any, Protocol

from covia.models import SecretExtractResult, SecretSetResult


class _SyncSecretVenue(Protocol):
    def run(self, operation: str, input: Any = None, *, timeout: float | None = None) -> Any: ...
    def list_secrets(self) -> list[str]: ...
    def put_secret(self, name: str, value: str) -> None: ...
    def delete_secret(self, name: str) -> None: ...


class _AsyncSecretVenue(Protocol):
    async def run(self, operation: str, input: Any = None, *, timeout: float | None = None) -> Any: ...
    async def list_secrets(self) -> list[str]: ...
    async def put_secret(self, name: str, value: str) -> None: ...
    async def delete_secret(self, name: str) -> None: ...


class SecretManager:
    """Sync accessor for venue secret storage.

    Do not instantiate directly — use ``venue.secrets``.
    """

    def __init__(self, venue: _SyncSecretVenue) -> None:
        self._venue = venue

    def list(self) -> list[str]:
        """List the names of secrets stored at this venue."""
        return self._venue.list_secrets()

    def put(self, name: str, value: str) -> None:
        """Store (or replace) a secret via the REST API."""
        self._venue.put_secret(name, value)

    def delete(self, name: str) -> None:
        """Delete a stored secret."""
        self._venue.delete_secret(name)

    def set(self, name: str, value: str) -> SecretSetResult:
        """Store a secret via ``v/ops/secret/set``."""
        return SecretSetResult.model_validate(self._venue.run("v/ops/secret/set", {"name": name, "value": value}))

    def extract(self, name: str) -> SecretExtractResult:
        """Extract a secret value via ``v/ops/secret/extract``.

        Requires a UCAN capability grant; the venue may reject this call
        without an appropriate capability proof.
        """
        return SecretExtractResult.model_validate(self._venue.run("v/ops/secret/extract", {"name": name}))


class AsyncSecretManager:
    """Async mirror of :class:`SecretManager`."""

    def __init__(self, venue: _AsyncSecretVenue) -> None:
        self._venue = venue

    async def list(self) -> list[str]:
        return await self._venue.list_secrets()

    async def put(self, name: str, value: str) -> None:
        await self._venue.put_secret(name, value)

    async def delete(self, name: str) -> None:
        await self._venue.delete_secret(name)

    async def set(self, name: str, value: str) -> SecretSetResult:
        return SecretSetResult.model_validate(await self._venue.run("v/ops/secret/set", {"name": name, "value": value}))

    async def extract(self, name: str) -> SecretExtractResult:
        return SecretExtractResult.model_validate(await self._venue.run("v/ops/secret/extract", {"name": name}))
