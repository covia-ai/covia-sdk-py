"""AgentManager — high-level typed wrapper around the ``v/ops/agent/*`` operations.

Obtained via :attr:`Venue.agents <covia.venue.Venue.agents>`. All methods
block until the underlying operation completes and validate the response
via :mod:`covia.models`.
"""

from __future__ import annotations

from typing import Any, Protocol

from covia.models import (
    AgentChatResult,
    AgentCreateResult,
    AgentDeleteResult,
    AgentListResult,
    AgentMessageResult,
    AgentQueryResult,
    AgentRequestResult,
    AgentSuspendResult,
    AgentTriggerResult,
)


class _SyncInvoker(Protocol):
    def run(self, operation: str, input: Any = None, *, timeout: float | None = None) -> Any: ...


class _AsyncInvoker(Protocol):
    async def run(self, operation: str, input: Any = None, *, timeout: float | None = None) -> Any: ...


def _drop_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


class AgentManager:
    """Sync accessor for ``v/ops/agent/*`` operations.

    Do not instantiate directly — use ``venue.agents``.
    """

    def __init__(self, venue: _SyncInvoker) -> None:
        self._venue = venue

    def create(
        self,
        agent_id: str,
        *,
        config: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
        overwrite: bool | None = None,
    ) -> AgentCreateResult:
        """Create an agent with the given id and optional config/state."""
        payload = _drop_none(
            {
                "agentId": agent_id,
                "config": config,
                "state": state,
                "overwrite": overwrite,
            }
        )
        return AgentCreateResult.model_validate(self._venue.run("v/ops/agent/create", payload))

    def request(
        self,
        agent_id: str,
        input: Any = None,
        *,
        wait: bool | float | None = None,
    ) -> AgentRequestResult:
        """Send a request to an agent.

        Args:
            agent_id: Target agent id.
            input: Request payload (shape is agent-specific).
            wait: ``True`` or a timeout in seconds to wait for the agent to
                respond. ``False`` or ``None`` returns immediately.
        """
        payload = _drop_none({"agentId": agent_id, "input": input, "wait": wait})
        return AgentRequestResult.model_validate(self._venue.run("v/ops/agent/request", payload))

    def message(self, agent_id: str, message: Any) -> AgentMessageResult:
        """Deliver a fire-and-forget message to an agent."""
        return AgentMessageResult.model_validate(
            self._venue.run("v/ops/agent/message", {"agentId": agent_id, "message": message})
        )

    def chat(
        self,
        agent_id: str,
        message: Any,
        session_id: str | None = None,
    ) -> AgentChatResult:
        """Send a message to an agent and block for its next response on the session.

        Session lifecycle:

        * Omit ``session_id`` on the first call — the server mints a session
          and returns its id in :attr:`AgentChatResult.sessionId`. Capture it.
        * Pass the returned ``session_id`` on every subsequent call to continue
          the conversation.
        * An unknown ``session_id`` is rejected (the server will not silently
          mint one); omit the argument to start a new session.

        Concurrency: only one chat may be in flight per session. Concurrent
        calls on the same session are rejected by the venue.
        """
        payload = _drop_none({"agentId": agent_id, "message": message, "sessionId": session_id})
        return AgentChatResult.model_validate(self._venue.run("v/ops/agent/chat", payload))

    def trigger(self, agent_id: str) -> AgentTriggerResult:
        """Fire any pending scheduled work for an agent."""
        return AgentTriggerResult.model_validate(self._venue.run("v/ops/agent/trigger", {"agentId": agent_id}))

    def query(self, agent_id: str) -> AgentQueryResult:
        """Get current status, state, config, and task list for an agent."""
        return AgentQueryResult.model_validate(self._venue.run("v/ops/agent/info", {"agentId": agent_id}))

    def list(self, *, include_terminated: bool | None = None) -> AgentListResult:
        """List agents on this venue."""
        payload = _drop_none({"includeTerminated": include_terminated})
        return AgentListResult.model_validate(self._venue.run("v/ops/agent/list", payload))

    def delete(self, agent_id: str, *, remove: bool | None = None) -> AgentDeleteResult:
        """Delete (or terminate) an agent."""
        payload = _drop_none({"agentId": agent_id, "remove": remove})
        return AgentDeleteResult.model_validate(self._venue.run("v/ops/agent/delete", payload))

    def suspend(self, agent_id: str) -> AgentSuspendResult:
        """Suspend an agent."""
        return AgentSuspendResult.model_validate(self._venue.run("v/ops/agent/suspend", {"agentId": agent_id}))

    def resume(self, agent_id: str, *, auto_wake: bool | None = None) -> AgentSuspendResult:
        """Resume a suspended agent."""
        payload = _drop_none({"agentId": agent_id, "autoWake": auto_wake})
        return AgentSuspendResult.model_validate(self._venue.run("v/ops/agent/resume", payload))

    def update(
        self,
        agent_id: str,
        *,
        config: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
    ) -> Any:
        """Update an agent's config and/or state."""
        payload = _drop_none({"agentId": agent_id, "config": config, "state": state})
        return self._venue.run("v/ops/agent/update", payload)

    def cancel_task(self, agent_id: str, task_id: str) -> Any:
        """Cancel a running task on an agent."""
        return self._venue.run(
            "v/ops/agent/cancel-task",
            {"agentId": agent_id, "taskId": task_id},
        )


class AsyncAgentManager:
    """Async mirror of :class:`AgentManager`."""

    def __init__(self, venue: _AsyncInvoker) -> None:
        self._venue = venue

    async def create(
        self,
        agent_id: str,
        *,
        config: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
        overwrite: bool | None = None,
    ) -> AgentCreateResult:
        payload = _drop_none(
            {
                "agentId": agent_id,
                "config": config,
                "state": state,
                "overwrite": overwrite,
            }
        )
        return AgentCreateResult.model_validate(await self._venue.run("v/ops/agent/create", payload))

    async def request(
        self,
        agent_id: str,
        input: Any = None,
        *,
        wait: bool | float | None = None,
    ) -> AgentRequestResult:
        payload = _drop_none({"agentId": agent_id, "input": input, "wait": wait})
        return AgentRequestResult.model_validate(await self._venue.run("v/ops/agent/request", payload))

    async def message(self, agent_id: str, message: Any) -> AgentMessageResult:
        return AgentMessageResult.model_validate(
            await self._venue.run("v/ops/agent/message", {"agentId": agent_id, "message": message})
        )

    async def chat(
        self,
        agent_id: str,
        message: Any,
        session_id: str | None = None,
    ) -> AgentChatResult:
        payload = _drop_none({"agentId": agent_id, "message": message, "sessionId": session_id})
        return AgentChatResult.model_validate(await self._venue.run("v/ops/agent/chat", payload))

    async def trigger(self, agent_id: str) -> AgentTriggerResult:
        return AgentTriggerResult.model_validate(await self._venue.run("v/ops/agent/trigger", {"agentId": agent_id}))

    async def query(self, agent_id: str) -> AgentQueryResult:
        return AgentQueryResult.model_validate(await self._venue.run("v/ops/agent/info", {"agentId": agent_id}))

    async def list(self, *, include_terminated: bool | None = None) -> AgentListResult:
        payload = _drop_none({"includeTerminated": include_terminated})
        return AgentListResult.model_validate(await self._venue.run("v/ops/agent/list", payload))

    async def delete(self, agent_id: str, *, remove: bool | None = None) -> AgentDeleteResult:
        payload = _drop_none({"agentId": agent_id, "remove": remove})
        return AgentDeleteResult.model_validate(await self._venue.run("v/ops/agent/delete", payload))

    async def suspend(self, agent_id: str) -> AgentSuspendResult:
        return AgentSuspendResult.model_validate(await self._venue.run("v/ops/agent/suspend", {"agentId": agent_id}))

    async def resume(self, agent_id: str, *, auto_wake: bool | None = None) -> AgentSuspendResult:
        payload = _drop_none({"agentId": agent_id, "autoWake": auto_wake})
        return AgentSuspendResult.model_validate(await self._venue.run("v/ops/agent/resume", payload))

    async def update(
        self,
        agent_id: str,
        *,
        config: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
    ) -> Any:
        payload = _drop_none({"agentId": agent_id, "config": config, "state": state})
        return await self._venue.run("v/ops/agent/update", payload)

    async def cancel_task(self, agent_id: str, task_id: str) -> Any:
        return await self._venue.run(
            "v/ops/agent/cancel-task",
            {"agentId": agent_id, "taskId": task_id},
        )
