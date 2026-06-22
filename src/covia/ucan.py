"""UCANManager — typed wrapper around ``v/ops/ucan/*`` operations.

UCAN (User-Controlled Authorisation Network) tokens are how a caller
delegates capabilities on lattice paths to another DID. Once issued, the
audience presents the token alongside invocations via
``venue.run(op, input, ucans=[token])`` so the venue can verify the
capability before serving the request.

Attenuations are path-scoped:

- ``with`` **must** be a fully-qualified DID URL in the caller's own
  namespace, e.g. ``did:key:z6Mk...alice/w/projects/acme`` or
  ``did:web:venue.covia.ai/o/my-transform``. The server rejects
  attenuations that don't start with ``<callerDID>/``.
- ``can`` is the ability verb. Canonical values: ``crud/read``,
  ``crud/write``, or ``*``. Ability prefixes cover verbs below them
  (``crud`` covers ``crud/read`` and ``crud/write``).

Expiry is a Unix timestamp (seconds); the venue rejects proofs after
that instant. The issue response is ``{"token": "<JWT>"}`` — pass
``token`` as an element of the ``ucans`` list on subsequent invokes.
"""

from __future__ import annotations

from typing import Any, Protocol

from covia.models import UCANAttenuation, UCANIssueResult


class _SyncInvoker(Protocol):
    def run(self, operation: str, input: Any = None, *, timeout: float | None = None) -> Any: ...


class _AsyncInvoker(Protocol):
    async def run(self, operation: str, input: Any = None, *, timeout: float | None = None) -> Any: ...


def _serialise_atts(atts: list[UCANAttenuation] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [a.model_dump(by_alias=True) if isinstance(a, UCANAttenuation) else a for a in atts]


class UCANManager:
    """Sync accessor for ``v/ops/ucan/*`` operations.

    Do not instantiate directly — use ``venue.ucan``.
    """

    def __init__(self, venue: _SyncInvoker) -> None:
        self._venue = venue

    def issue(
        self,
        audience: str,
        attenuations: list[UCANAttenuation] | list[dict[str, Any]],
        expiry: int,
    ) -> UCANIssueResult:
        """Issue a UCAN delegation to ``audience`` with the given capabilities.

        Args:
            audience: Target DID.
            attenuations: List of ``{"with": resource, "can": ability}`` grants.
            expiry: Unix timestamp (seconds) after which the UCAN is no longer valid.

        Returns:
            A :class:`~covia.models.UCANIssueResult` carrying the issued
            ``token``.
        """
        return UCANIssueResult.model_validate(
            self._venue.run(
                "v/ops/ucan/issue",
                {"aud": audience, "att": _serialise_atts(attenuations), "exp": expiry},
            )
        )


class AsyncUCANManager:
    """Async mirror of :class:`UCANManager`."""

    def __init__(self, venue: _AsyncInvoker) -> None:
        self._venue = venue

    async def issue(
        self,
        audience: str,
        attenuations: list[UCANAttenuation] | list[dict[str, Any]],
        expiry: int,
    ) -> UCANIssueResult:
        return UCANIssueResult.model_validate(
            await self._venue.run(
                "v/ops/ucan/issue",
                {"aud": audience, "att": _serialise_atts(attenuations), "exp": expiry},
            )
        )
