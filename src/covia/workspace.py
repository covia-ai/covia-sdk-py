"""WorkspaceManager — typed wrapper around the ``v/ops/covia/*`` lattice operations.

Covia addresses its lattice by ``<DID>/<namespace>/<path...>``. Within a
session the caller's DID is implicit, so paths can be written as
``/<namespace>/<sub-path>``. To read another user's data (with a UCAN
proof) pass a fully-qualified ``<their-DID>/<namespace>/<path>``.

Namespaces accepted by ``covia:*`` (hardcoded in the server's lattice app):

========  ==========================  =============================  ==============
Prefix    Purpose                     Mutability                     User-writable?
========  ==========================  =============================  ==============
``/a/``   Assets (content-addressed)  immutable, write-once           no
``/o/``   Operations (named registry) mutable, schema-enforced        yes
``/j/``   Jobs (lifecycle records)    system-managed                  no
``/g/``   Agents (identity-bound)     system-managed                  no
``/w/``   Workspace (freely mutable)  freely mutable                  yes
``/s/``   Secrets (encrypted)         capability-gated                via ``secret:*`` only
========  ==========================  =============================  ==============

Virtual namespaces — resolved against the active ``RequestContext`` and
only meaningful when the caller is running under an agent/session/job:

========  ==========================================
Prefix    Scope
========  ==========================================
``/n/``   Agent-scoped scratch (persistent)
``/c/``   Session-scoped scratch (per conversation)
``/t/``   Job-scoped scratch (per invocation, inherited by sub-ops)
``/v/``   Venue globals
========  ==========================================

Only ``/w/`` and ``/o/`` accept direct user writes via
``workspace.write`` / ``workspace.delete`` / ``workspace.append``. Writes
into any other namespace go through their dedicated operations (e.g.
``venue.secrets.set`` for ``/s/``, ``venue.agents.*`` for ``/g/``).

See ``venue/docs/GRID_LATTICE_DESIGN.md`` in the covia repository for
the full addressing specification.
"""

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
    """Sync accessor for ``v/ops/covia/*`` lattice operations.

    Do not instantiate directly — use ``venue.workspace``. See the module
    docstring for namespace semantics.
    """

    def __init__(self, venue: _SyncInvoker) -> None:
        self._venue = venue

    def read(self, path: str, *, max_size: int | None = None) -> WorkspaceReadResult:
        """Read the value at *path*.

        *path* is resolved against the caller's DID unless fully qualified
        (``did:key:...`` / ``did:web:...`` prefix). Cross-DID reads require
        a UCAN capability proof — pass the token via ``venue.run`` with
        ``ucans=[...]`` or via a direct ``venue.invoke`` call.

        ``max_size`` caps the encoded response size (default ~1 MB server
        side). If exceeded, the result returns
        ``exists=True, value=None, truncated=True, size=<bytes>``; pair
        with :meth:`list` or :meth:`slice` to page through large values.
        """
        payload = _drop_none({"path": path, "maxSize": max_size})
        return WorkspaceReadResult.model_validate(self._venue.run("v/ops/covia/read", payload))

    def write(self, path: str, value: Any) -> WorkspaceWriteResult:
        """Overwrite the value at *path*.

        Writes are only accepted in the user-writable namespaces (``/w/``
        and ``/o/``). Writing under ``/a/``, ``/j/``, ``/g/``, or ``/s/``
        is rejected by the server — use the dedicated operations instead.
        """
        return WorkspaceWriteResult.model_validate(self._venue.run("v/ops/covia/write", {"path": path, "value": value}))

    def delete(self, path: str) -> WorkspaceDeleteResult:
        """Delete the entry at *path* (``/w/`` and ``/o/`` only)."""
        return WorkspaceDeleteResult.model_validate(self._venue.run("v/ops/covia/delete", {"path": path}))

    def append(self, path: str, value: Any) -> WorkspaceAppendResult:
        """Append *value* to the collection at *path*.

        The target must be a vector-typed node (or absent — the server
        will create one). Appends are commutative across concurrent
        callers, per the lattice merge semantics.
        """
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
        """List the direct children under *path*.

        Omit *path* to list the top-level namespaces visible to the
        caller. The result's ``type`` field distinguishes maps (``keys``
        populated) from lists (``values`` populated).
        """
        payload = _drop_none({"path": path, "limit": limit, "offset": offset})
        return WorkspaceListResult.model_validate(self._venue.run("v/ops/covia/list", payload))

    def slice(
        self,
        path: str,
        *,
        offset: int | None = None,
        limit: int | None = None,
    ) -> WorkspaceSliceResult:
        """Take a windowed slice of a vector-valued node at *path*.

        Use this to page through large collections that
        :meth:`read` would truncate.
        """
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
