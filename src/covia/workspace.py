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
    WorkspaceAggregateResult,
    WorkspaceAppendResult,
    WorkspaceCountResult,
    WorkspaceDeleteResult,
    WorkspaceInspectResult,
    WorkspaceListResult,
    WorkspaceReadResult,
    WorkspaceSliceResult,
    WorkspaceWriteResult,
)

# Aliases defined here (module scope) so `list` resolves to the builtin — the
# manager classes below define a `list()` method that would otherwise shadow it
# in their own annotations.
_Ucans = list[str] | None
_Paths = str | list[str]


class _SyncInvoker(Protocol):
    def run(self, operation: str, input: Any = None, *, timeout: float | None = None, ucans: _Ucans = None) -> Any: ...
    def _get_value(self, op: str, params: dict[str, Any]) -> dict[str, Any]: ...


class _AsyncInvoker(Protocol):
    async def run(
        self, operation: str, input: Any = None, *, timeout: float | None = None, ucans: _Ucans = None
    ) -> Any: ...
    async def _get_value(self, op: str, params: dict[str, Any]) -> dict[str, Any]: ...


def _drop_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


class WorkspaceManager:
    """Sync accessor for ``v/ops/covia/*`` lattice operations.

    Do not instantiate directly — use ``venue.workspace``. See the module
    docstring for namespace semantics.

    The ``workspace`` name is provisional: this accessor spans *all* covia
    namespaces (``/w/``, ``/o/``, ``/a/``, ``/g/`` …), not just ``/w/``, so a
    future release may rename it or add an alias (most likely ``venue.values``).
    ``venue.workspace`` will keep working either way.
    """

    def __init__(self, venue: _SyncInvoker) -> None:
        self._venue = venue

    def read(self, path: str, *, max_size: int | None = None, ucans: _Ucans = None) -> WorkspaceReadResult:
        """Read the value at *path*.

        *path* is resolved against the caller's DID unless fully qualified
        (``did:key:...`` / ``did:web:...`` prefix). To read **another DID's**
        data, build the path with :func:`covia.did.did_url` and pass the
        capability proof as ``ucans=[token]``.

        ``max_size`` caps the encoded response size (default ~1 MB server
        side). If exceeded, the result returns
        ``exists=True, value=None, truncated=True, valueBytes=<bytes>``; pair
        with :meth:`list` or :meth:`slice` to page through large values.
        """
        params: dict[str, Any] = {"path": path, "maxSize": max_size}
        if ucans:  # proof tokens ride only on the invoke transport
            return WorkspaceReadResult.model_validate(
                self._venue.run("v/ops/covia/read", _drop_none(params), ucans=ucans)
            )
        return WorkspaceReadResult.model_validate(self._venue._get_value("read", params))

    def write(self, path: str, value: Any, *, ucans: _Ucans = None) -> WorkspaceWriteResult:
        """Overwrite the value at *path*.

        Writes are only accepted in the user-writable namespaces (``/w/``
        and ``/o/``). Writing under ``/a/``, ``/j/``, ``/g/``, or ``/s/``
        is rejected by the server — use the dedicated operations instead.
        Writing into another DID's namespace requires a ``crud/write`` proof
        in ``ucans``.
        """
        return WorkspaceWriteResult.model_validate(
            self._venue.run("v/ops/covia/write", {"path": path, "value": value}, ucans=ucans)
        )

    def delete(self, path: str, *, ucans: _Ucans = None) -> WorkspaceDeleteResult:
        """Delete the entry at *path* (``/w/`` and ``/o/`` only)."""
        return WorkspaceDeleteResult.model_validate(self._venue.run("v/ops/covia/delete", {"path": path}, ucans=ucans))

    def append(self, path: str, value: Any, *, ucans: _Ucans = None) -> WorkspaceAppendResult:
        """Append *value* to the collection at *path*.

        The target must be a vector-typed node (or absent — the server
        will create one). Appends are commutative across concurrent
        callers, per the lattice merge semantics.
        """
        return WorkspaceAppendResult.model_validate(
            self._venue.run("v/ops/covia/append", {"path": path, "value": value}, ucans=ucans)
        )

    def list(
        self,
        path: str | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
        ucans: _Ucans = None,
    ) -> WorkspaceListResult:
        """List the direct children under *path*.

        Omit *path* to list the top-level namespaces visible to the
        caller. The result's ``type`` field distinguishes maps (``keys``
        populated) from lists (``values`` populated).
        """
        params: dict[str, Any] = {"path": path, "limit": limit, "offset": offset}
        if ucans or path is None:  # the GET route requires a path; a root list uses invoke
            return WorkspaceListResult.model_validate(
                self._venue.run("v/ops/covia/list", _drop_none(params), ucans=ucans)
            )
        return WorkspaceListResult.model_validate(self._venue._get_value("list", params))

    def slice(
        self,
        path: str,
        *,
        offset: int | None = None,
        limit: int | None = None,
        ucans: _Ucans = None,
    ) -> WorkspaceSliceResult:
        """Take a windowed slice of a vector-valued node at *path*.

        Use this to page through large collections that
        :meth:`read` would truncate.
        """
        params: dict[str, Any] = {"path": path, "offset": offset, "limit": limit}
        if ucans:
            return WorkspaceSliceResult.model_validate(
                self._venue.run("v/ops/covia/slice", _drop_none(params), ucans=ucans)
            )
        return WorkspaceSliceResult.model_validate(self._venue._get_value("slice", params))

    def inspect(
        self,
        paths: _Paths,
        *,
        budget: int | None = None,
        compact: bool | None = None,
        ucans: _Ucans = None,
    ) -> WorkspaceInspectResult:
        """Budget-bounded JSON5 render of *paths* — the primary discovery tool.

        A single path is job-free (``GET /values/inspect``); passing a list of
        paths (or a UCAN proof) uses the op path. ``budget`` caps the rendered
        bytes; ``compact`` toggles single-line output.
        """
        if ucans or isinstance(paths, list):
            payload = _drop_none({"paths": paths, "budget": budget, "compact": compact})
            return WorkspaceInspectResult.model_validate(self._venue.run("v/ops/covia/inspect", payload, ucans=ucans))
        return WorkspaceInspectResult.model_validate(
            self._venue._get_value("inspect", {"path": paths, "budget": budget, "compact": compact})
        )

    def count(self, path: str, *, depth: int | None = None, ucans: _Ucans = None) -> WorkspaceCountResult:
        """Count the entries *depth* levels below *path* — a job-free server-side
        tally, so the caller never reads every record to learn "how many".

        ``depth`` is the number of ``get``-steps below *path* (default 1 = direct
        children); records nested at ``w/x/<bucket>/<record>`` are counted with
        ``depth=2``. An absent path or a scalar returns ``exists=False``.
        """
        params: dict[str, Any] = {"path": path, "depth": depth}
        if ucans:
            return WorkspaceCountResult.model_validate(
                self._venue.run("v/ops/covia/aggregate", _drop_none(params), ucans=ucans)
            )
        return WorkspaceCountResult.model_validate(self._venue._get_value("count", params))

    def aggregate(
        self,
        path: str,
        *,
        depth: int | None = None,
        group_by: str | None = None,
        ucans: _Ucans = None,
    ) -> WorkspaceAggregateResult:
        """Count entries *depth* levels below *path*, optionally partitioned by a
        field — the job-free, authoritative alternative to counting client-side.

        ``group_by`` names the field whose value forms each group key (may be a
        relative path, ``foo/bar``); an entry missing it groups under ``"null"``.
        Σ(group counts) equals the top-level ``count``.
        """
        params: dict[str, Any] = {"path": path, "depth": depth, "groupBy": group_by}
        if ucans:
            return WorkspaceAggregateResult.model_validate(
                self._venue.run("v/ops/covia/aggregate", _drop_none(params), ucans=ucans)
            )
        return WorkspaceAggregateResult.model_validate(self._venue._get_value("aggregate", params))


class AsyncWorkspaceManager:
    """Async mirror of :class:`WorkspaceManager`."""

    def __init__(self, venue: _AsyncInvoker) -> None:
        self._venue = venue

    async def read(self, path: str, *, max_size: int | None = None, ucans: _Ucans = None) -> WorkspaceReadResult:
        params: dict[str, Any] = {"path": path, "maxSize": max_size}
        if ucans:
            return WorkspaceReadResult.model_validate(
                await self._venue.run("v/ops/covia/read", _drop_none(params), ucans=ucans)
            )
        return WorkspaceReadResult.model_validate(await self._venue._get_value("read", params))

    async def write(self, path: str, value: Any, *, ucans: _Ucans = None) -> WorkspaceWriteResult:
        return WorkspaceWriteResult.model_validate(
            await self._venue.run("v/ops/covia/write", {"path": path, "value": value}, ucans=ucans)
        )

    async def delete(self, path: str, *, ucans: _Ucans = None) -> WorkspaceDeleteResult:
        return WorkspaceDeleteResult.model_validate(
            await self._venue.run("v/ops/covia/delete", {"path": path}, ucans=ucans)
        )

    async def append(self, path: str, value: Any, *, ucans: _Ucans = None) -> WorkspaceAppendResult:
        return WorkspaceAppendResult.model_validate(
            await self._venue.run("v/ops/covia/append", {"path": path, "value": value}, ucans=ucans)
        )

    async def list(
        self,
        path: str | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
        ucans: _Ucans = None,
    ) -> WorkspaceListResult:
        params: dict[str, Any] = {"path": path, "limit": limit, "offset": offset}
        if ucans or path is None:
            return WorkspaceListResult.model_validate(
                await self._venue.run("v/ops/covia/list", _drop_none(params), ucans=ucans)
            )
        return WorkspaceListResult.model_validate(await self._venue._get_value("list", params))

    async def slice(
        self,
        path: str,
        *,
        offset: int | None = None,
        limit: int | None = None,
        ucans: _Ucans = None,
    ) -> WorkspaceSliceResult:
        params: dict[str, Any] = {"path": path, "offset": offset, "limit": limit}
        if ucans:
            return WorkspaceSliceResult.model_validate(
                await self._venue.run("v/ops/covia/slice", _drop_none(params), ucans=ucans)
            )
        return WorkspaceSliceResult.model_validate(await self._venue._get_value("slice", params))

    async def inspect(
        self,
        paths: _Paths,
        *,
        budget: int | None = None,
        compact: bool | None = None,
        ucans: _Ucans = None,
    ) -> WorkspaceInspectResult:
        if ucans or isinstance(paths, list):
            payload = _drop_none({"paths": paths, "budget": budget, "compact": compact})
            return WorkspaceInspectResult.model_validate(
                await self._venue.run("v/ops/covia/inspect", payload, ucans=ucans)
            )
        return WorkspaceInspectResult.model_validate(
            await self._venue._get_value("inspect", {"path": paths, "budget": budget, "compact": compact})
        )

    async def count(self, path: str, *, depth: int | None = None, ucans: _Ucans = None) -> WorkspaceCountResult:
        params: dict[str, Any] = {"path": path, "depth": depth}
        if ucans:
            return WorkspaceCountResult.model_validate(
                await self._venue.run("v/ops/covia/aggregate", _drop_none(params), ucans=ucans)
            )
        return WorkspaceCountResult.model_validate(await self._venue._get_value("count", params))

    async def aggregate(
        self,
        path: str,
        *,
        depth: int | None = None,
        group_by: str | None = None,
        ucans: _Ucans = None,
    ) -> WorkspaceAggregateResult:
        params: dict[str, Any] = {"path": path, "depth": depth, "groupBy": group_by}
        if ucans:
            return WorkspaceAggregateResult.model_validate(
                await self._venue.run("v/ops/covia/aggregate", _drop_none(params), ucans=ucans)
            )
        return WorkspaceAggregateResult.model_validate(await self._venue._get_value("aggregate", params))
