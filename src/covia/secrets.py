"""SecretManager — typed wrapper for venue-scoped secret storage.

Secrets live in the ``/s/`` namespace of the caller's lattice. They are
encrypted at rest and **capability-gated** — reads (``extract``) always
require a UCAN proof, even for the owner, because operations that
reference secrets by name (``s/NAME``) resolve them through the same
capability check.

The manager exposes two surfaces:

- **REST** (``list``, ``put``, ``delete``) — manage the owner's own
  secrets via ``/api/v1/secrets/*``. Authenticated as the caller.
- **Operations** (``set``, ``extract``) — the ``v/ops/secret/*`` ops.
  ``set`` stores under the caller's ``/s/``; ``extract`` resolves a
  secret by name and requires a UCAN capability grant on the target.
"""

from __future__ import annotations

from typing import Any, Protocol

from covia.models import SecretExtractResult, SecretSetResult

# Alias at module scope so `list` resolves to the builtin — SecretManager
# defines a `list()` method that would otherwise shadow it in annotations.
_Ucans = list[str] | None


class _SyncSecretVenue(Protocol):
    def run(self, operation: str, input: Any = None, *, timeout: float | None = None, ucans: _Ucans = None) -> Any: ...
    def list_secrets(self) -> list[str]: ...
    def put_secret(self, name: str, value: str) -> None: ...
    def delete_secret(self, name: str) -> None: ...


class _AsyncSecretVenue(Protocol):
    async def run(
        self, operation: str, input: Any = None, *, timeout: float | None = None, ucans: _Ucans = None
    ) -> Any: ...
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

    def extract(self, name: str, *, ucans: _Ucans = None) -> SecretExtractResult:
        """Extract a secret value via ``v/ops/secret/extract``.

        Requires a UCAN capability grant — pass the proof token(s) as
        ``ucans=[token]``. Extracting another DID's secret needs a grant on
        that DID's ``/s/<name>`` resource.
        """
        return SecretExtractResult.model_validate(self._venue.run("v/ops/secret/extract", {"name": name}, ucans=ucans))


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

    async def extract(self, name: str, *, ucans: _Ucans = None) -> SecretExtractResult:
        return SecretExtractResult.model_validate(
            await self._venue.run("v/ops/secret/extract", {"name": name}, ucans=ucans)
        )
