"""UCANManager — typed wrapper around ``v/ops/ucan/*`` operations."""

from __future__ import annotations

from typing import Any, Protocol

from covia.models import UCANAttenuation


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
    ) -> Any:
        """Issue a UCAN delegation to ``audience`` with the given capabilities.

        Args:
            audience: Target DID.
            attenuations: List of ``{"with": resource, "can": ability}`` grants.
            expiry: Unix timestamp (seconds) after which the UCAN is no longer valid.

        Returns:
            Raw venue response (shape is backend-defined, typically a dict).
        """
        return self._venue.run(
            "v/ops/ucan/issue",
            {"aud": audience, "att": _serialise_atts(attenuations), "exp": expiry},
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
    ) -> Any:
        return await self._venue.run(
            "v/ops/ucan/issue",
            {"aud": audience, "att": _serialise_atts(attenuations), "exp": expiry},
        )
