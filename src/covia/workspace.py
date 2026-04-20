"""WorkspaceManager — typed wrapper around the ``v/ops/covia/*`` workspace operations."""

from __future__ import annotations

from typing import Any, Protocol

from covia.models import (
    WorkspaceAppendResult,
    WorkspaceDeleteResult,
    WorkspaceListResult,
    WorkspaceReadResult,
    WorkspaceSliceResult,
    WorkspaceWriteResult,
)


class _SyncInvoker(Protocol):
    def run(self, operation: str, input: Any = None, *, timeout: float | None = None) -> Any: ...


class _AsyncInvoker(Protocol):
    async def run(self, operation: str, input: Any = None, *, timeout: float | None = None) -> Any: ...


def _drop_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


class WorkspaceManager:
    """Sync accessor for ``v/ops/covia/*`` workspace operations.

    Do not instantiate directly — use ``venue.workspace``.
    """

    def __init__(self, venue: _SyncInvoker) -> None:
        self._venue = venue

    def read(self, path: str, *, max_size: int | None = None) -> WorkspaceReadResult:
        """Read a value from the workspace."""
        payload = _drop_none({"path": path, "maxSize": max_size})
        return WorkspaceReadResult.model_validate(self._venue.run("v/ops/covia/read", payload))

    def write(self, path: str, value: Any) -> WorkspaceWriteResult:
        """Write (overwrite) a value at the given path."""
        return WorkspaceWriteResult.model_validate(self._venue.run("v/ops/covia/write", {"path": path, "value": value}))

    def delete(self, path: str) -> WorkspaceDeleteResult:
        """Delete the entry at the given path."""
        return WorkspaceDeleteResult.model_validate(self._venue.run("v/ops/covia/delete", {"path": path}))

    def append(self, path: str, value: Any) -> WorkspaceAppendResult:
        """Append a value to a collection at the given path."""
        return WorkspaceAppendResult.model_validate(
            self._venue.run("v/ops/covia/append", {"path": path, "value": value})
        )

    def list(
        self,
        path: str | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> WorkspaceListResult:
        """List entries under a path."""
        payload = _drop_none({"path": path, "limit": limit, "offset": offset})
        return WorkspaceListResult.model_validate(self._venue.run("v/ops/covia/list", payload))

    def slice(
        self,
        path: str,
        *,
        offset: int | None = None,
        limit: int | None = None,
    ) -> WorkspaceSliceResult:
        """Take a slice of a collection at a path."""
        payload = _drop_none({"path": path, "offset": offset, "limit": limit})
        return WorkspaceSliceResult.model_validate(self._venue.run("v/ops/covia/slice", payload))


class AsyncWorkspaceManager:
    """Async mirror of :class:`WorkspaceManager`."""

    def __init__(self, venue: _AsyncInvoker) -> None:
        self._venue = venue

    async def read(self, path: str, *, max_size: int | None = None) -> WorkspaceReadResult:
        payload = _drop_none({"path": path, "maxSize": max_size})
        return WorkspaceReadResult.model_validate(await self._venue.run("v/ops/covia/read", payload))

    async def write(self, path: str, value: Any) -> WorkspaceWriteResult:
        return WorkspaceWriteResult.model_validate(
            await self._venue.run("v/ops/covia/write", {"path": path, "value": value})
        )

    async def delete(self, path: str) -> WorkspaceDeleteResult:
        return WorkspaceDeleteResult.model_validate(await self._venue.run("v/ops/covia/delete", {"path": path}))

    async def append(self, path: str, value: Any) -> WorkspaceAppendResult:
        return WorkspaceAppendResult.model_validate(
            await self._venue.run("v/ops/covia/append", {"path": path, "value": value})
        )

    async def list(
        self,
        path: str | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> WorkspaceListResult:
        payload = _drop_none({"path": path, "limit": limit, "offset": offset})
        return WorkspaceListResult.model_validate(await self._venue.run("v/ops/covia/list", payload))

    async def slice(
        self,
        path: str,
        *,
        offset: int | None = None,
        limit: int | None = None,
    ) -> WorkspaceSliceResult:
        payload = _drop_none({"path": path, "offset": offset, "limit": limit})
        return WorkspaceSliceResult.model_validate(await self._venue.run("v/ops/covia/slice", payload))
