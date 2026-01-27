"""Server-Sent Events support for streaming job updates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SSEEvent:
    """A single server-sent event received from a Covia venue."""

    event: str | None = None
    data: str = ""
    id: str | None = None
    retry: int | None = None

    @property
    def json(self) -> Any:
        """Parse the event data as JSON."""
        import json

        return json.loads(self.data)
