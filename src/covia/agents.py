"""Agent operations — the ``v/ops/agent/*`` surface.

:class:`AgentManager` (obtained via :attr:`Venue.agents
<covia.venue.Venue.agents>`) is the id-keyed wrapper; :class:`Agent`
(obtained via :meth:`Venue.agent <covia.venue.Venue.agent>`) is a lightweight
handle that binds one ``agent_id`` and delegates to it, plus :class:`ChatSession`
for multi-turn chat that auto-captures the session id. All methods block until
the underlying operation completes and validate the response via
:mod:`covia.models`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from covia.exceptions import GridError, NotFoundError
from covia.models import (
    AgentChatResult,
    AgentCompleteTaskResult,
    AgentCreateResult,
    AgentDeleteResult,
    AgentFailTaskResult,
    AgentForkResult,
    AgentInfoResult,
    AgentListResult,
    AgentMessageResult,
    AgentRequestResult,
    AgentSuspendResult,
    AgentTriggerResult,
)

if TYPE_CHECKING:
    from covia.async_api.venue import AsyncVenue
    from covia.venue import Venue


class _SyncInvoker(Protocol):
    def run(self, operation: str, input: Any = None, *, timeout: float | None = None) -> Any: ...
    def _get_agents(self, suffix: str, params: dict[str, Any]) -> dict[str, Any]: ...


class _AsyncInvoker(Protocol):
    async def run(self, operation: str, input: Any = None, *, timeout: float | None = None) -> Any: ...
    async def _get_agents(self, suffix: str, params: dict[str, Any]) -> dict[str, Any]: ...


def _drop_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


class AgentManager:
    """Sync accessor for ``v/ops/agent/*`` operations.

    Do not instantiate directly — use ``venue.agents``.
    """

    def __init__(self, venue: _SyncInvoker) -> None:
        self._venue = venue
        # GET /api/v1/agents support — flipped on the first 404 (pre-0.4 venue).
        self._agents_get_supported = True

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

    def info(self, agent_id: str) -> AgentInfoResult:
        """A lightweight status/config summary for an agent.

        **Job-free** on covia ≥ 0.4 (``GET /api/v1/agents/{id}``, covia #180);
        older venues transparently fall back to the invoke path (one probe,
        remembered)."""
        data = self._agents_get(f"/{agent_id}", {}, lambda: self._venue.run("v/ops/agent/info", {"agentId": agent_id}))
        return AgentInfoResult.model_validate(data)

    def list(self, *, include_terminated: bool | None = None) -> AgentListResult:
        """List agents on this venue.

        **Job-free** on covia ≥ 0.4 (``GET /api/v1/agents``, covia #180);
        older venues transparently fall back to the invoke path."""
        params = _drop_none({"includeTerminated": include_terminated})
        data = self._agents_get("", params, lambda: self._venue.run("v/ops/agent/list", params))
        return AgentListResult.model_validate(data)

    def _agents_get(self, suffix: str, params: dict[str, Any], fallback: Any) -> Any:
        """A job-free agents GET, falling back to the invoke path on pre-0.4
        venues — the GET surface 404s there, and only there (an unknown agent
        id is a structured error, not a bare 404). The probe result is
        remembered so old venues pay it once."""
        if self._agents_get_supported:
            try:
                return self._venue._get_agents(suffix, params)
            except NotFoundError:
                self._agents_get_supported = False
            except GridError as exc:
                if exc.status_code != 404:
                    raise
                self._agents_get_supported = False
        return fallback()

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

    def fork(
        self,
        source_id: str,
        agent_id: str,
        *,
        config: dict[str, Any] | None = None,
        include_timeline: bool | None = None,
        overwrite: bool | None = None,
    ) -> AgentForkResult:
        """Fork *source_id* into a new agent *agent_id* (``v/ops/agent/fork``)."""
        payload = _drop_none(
            {
                "sourceId": source_id,
                "agentId": agent_id,
                "config": config,
                "includeTimeline": include_timeline,
                "overwrite": overwrite,
            }
        )
        return AgentForkResult.model_validate(self._venue.run("v/ops/agent/fork", payload))

    def context(self, agent_id: str, task: Any = None) -> str:
        """Render the agent's context to a string (``v/ops/agent/context``)."""
        result: str = self._venue.run("v/ops/agent/context", _drop_none({"agentId": agent_id, "task": task}))
        return result

    def complete_task(self, result: Any = None) -> AgentCompleteTaskResult:
        """Complete the current in-scope task (``v/ops/agent/complete-task``)."""
        return AgentCompleteTaskResult.model_validate(
            self._venue.run("v/ops/agent/complete-task", _drop_none({"result": result}))
        )

    def fail_task(self, error: str) -> AgentFailTaskResult:
        """Fail the current in-scope task (``v/ops/agent/fail-task``)."""
        return AgentFailTaskResult.model_validate(self._venue.run("v/ops/agent/fail-task", {"error": error}))


class AsyncAgentManager:
    """Async mirror of :class:`AgentManager`."""

    def __init__(self, venue: _AsyncInvoker) -> None:
        self._venue = venue
        # GET /api/v1/agents support — flipped on the first 404 (pre-0.4 venue).
        self._agents_get_supported = True

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

    async def info(self, agent_id: str) -> AgentInfoResult:
        """A lightweight status/config summary for an agent (job-free on
        covia ≥ 0.4, covia #180; older venues fall back to the invoke path)."""
        data = await self._agents_get(
            f"/{agent_id}", {}, lambda: self._venue.run("v/ops/agent/info", {"agentId": agent_id})
        )
        return AgentInfoResult.model_validate(data)

    async def list(self, *, include_terminated: bool | None = None) -> AgentListResult:
        """List agents on this venue (job-free on covia ≥ 0.4, covia #180;
        older venues fall back to the invoke path)."""
        params = _drop_none({"includeTerminated": include_terminated})
        data = await self._agents_get("", params, lambda: self._venue.run("v/ops/agent/list", params))
        return AgentListResult.model_validate(data)

    async def _agents_get(self, suffix: str, params: dict[str, Any], fallback: Any) -> Any:
        """A job-free agents GET, falling back to the invoke path on pre-0.4
        venues (404 probe, remembered)."""
        if self._agents_get_supported:
            try:
                return await self._venue._get_agents(suffix, params)
            except NotFoundError:
                self._agents_get_supported = False
            except GridError as exc:
                if exc.status_code != 404:
                    raise
                self._agents_get_supported = False
        return await fallback()

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

    async def fork(
        self,
        source_id: str,
        agent_id: str,
        *,
        config: dict[str, Any] | None = None,
        include_timeline: bool | None = None,
        overwrite: bool | None = None,
    ) -> AgentForkResult:
        payload = _drop_none(
            {
                "sourceId": source_id,
                "agentId": agent_id,
                "config": config,
                "includeTimeline": include_timeline,
                "overwrite": overwrite,
            }
        )
        return AgentForkResult.model_validate(await self._venue.run("v/ops/agent/fork", payload))

    async def context(self, agent_id: str, task: Any = None) -> str:
        result: str = await self._venue.run("v/ops/agent/context", _drop_none({"agentId": agent_id, "task": task}))
        return result

    async def complete_task(self, result: Any = None) -> AgentCompleteTaskResult:
        return AgentCompleteTaskResult.model_validate(
            await self._venue.run("v/ops/agent/complete-task", _drop_none({"result": result}))
        )

    async def fail_task(self, error: str) -> AgentFailTaskResult:
        return AgentFailTaskResult.model_validate(await self._venue.run("v/ops/agent/fail-task", {"error": error}))


class Agent:
    """A lightweight handle to a single agent on a venue.

    Obtained via :meth:`Venue.agent <covia.venue.Venue.agent>`. Binds an
    ``agent_id`` and delegates to the venue's :class:`AgentManager`, so
    ``venue.agent("a").info()`` reads the same as ``venue.agents.info("a")``.

    Task-scoped operations (``complete_task`` / ``fail_task``) are intentionally
    not on the handle — they act on the in-scope task from the request context,
    not a named agent; use :class:`AgentManager` for those.
    """

    def __init__(self, agent_id: str, venue: Venue) -> None:
        self.id = agent_id
        self.venue = venue
        self._agents: AgentManager = venue.agents

    def request(self, input: Any = None, *, wait: bool | float | None = None) -> AgentRequestResult:
        """Send a request to this agent (see :meth:`AgentManager.request`)."""
        return self._agents.request(self.id, input, wait=wait)

    def message(self, message: Any) -> AgentMessageResult:
        """Deliver a fire-and-forget message to this agent."""
        return self._agents.message(self.id, message)

    def chat(self, message: Any, session_id: str | None = None) -> AgentChatResult:
        """Send a message and block for this agent's next response on the session."""
        return self._agents.chat(self.id, message, session_id)

    def chat_session(self, session_id: str | None = None) -> ChatSession:
        """A :class:`ChatSession` bound to this agent (optionally resuming *session_id*)."""
        return ChatSession(self, session_id)

    def trigger(self) -> AgentTriggerResult:
        """Fire any pending scheduled work for this agent."""
        return self._agents.trigger(self.id)

    def info(self) -> AgentInfoResult:
        """A lightweight status/config summary for this agent."""
        return self._agents.info(self.id)

    def suspend(self) -> AgentSuspendResult:
        """Suspend this agent."""
        return self._agents.suspend(self.id)

    def resume(self, *, auto_wake: bool | None = None) -> AgentSuspendResult:
        """Resume this suspended agent."""
        return self._agents.resume(self.id, auto_wake=auto_wake)

    def update(
        self,
        *,
        config: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
    ) -> Any:
        """Update this agent's config and/or state."""
        return self._agents.update(self.id, config=config, state=state)

    def cancel_task(self, task_id: str) -> Any:
        """Cancel a running task on this agent."""
        return self._agents.cancel_task(self.id, task_id)

    def fork(
        self,
        agent_id: str,
        *,
        config: dict[str, Any] | None = None,
        include_timeline: bool | None = None,
        overwrite: bool | None = None,
    ) -> Agent:
        """Fork this agent into a new agent *agent_id*, returning its handle."""
        self._agents.fork(
            self.id,
            agent_id,
            config=config,
            include_timeline=include_timeline,
            overwrite=overwrite,
        )
        return Agent(agent_id, self.venue)

    def context(self, task: Any = None) -> str:
        """Render this agent's context to a string."""
        return self._agents.context(self.id, task)

    def delete(self, *, remove: bool | None = None) -> AgentDeleteResult:
        """Delete (or terminate) this agent."""
        return self._agents.delete(self.id, remove=remove)

    def __repr__(self) -> str:
        return f"Agent(id={self.id!r})"


class ChatSession:
    """A multi-turn chat with an :class:`Agent` that tracks the session id.

    The venue mints a session on the first :meth:`send` (when none is set);
    the returned id is captured and reused on every subsequent call. Pass an
    existing *session_id* to the constructor to resume a prior conversation.
    """

    def __init__(self, agent: Agent, session_id: str | None = None) -> None:
        self.agent = agent
        self._session_id = session_id

    @property
    def session_id(self) -> str | None:
        """The active session id, or ``None`` before the first :meth:`send`."""
        return self._session_id

    def send(self, message: Any) -> AgentChatResult:
        """Send *message* on this session, capturing the session id from the reply."""
        result = self.agent.chat(message, self._session_id)
        self._session_id = result.sessionId
        return result


class AsyncAgent:
    """Async mirror of :class:`Agent`. Obtained via
    :meth:`AsyncVenue.agent <covia.async_api.venue.AsyncVenue.agent>`."""

    def __init__(self, agent_id: str, venue: AsyncVenue) -> None:
        self.id = agent_id
        self.venue = venue
        self._agents: AsyncAgentManager = venue.agents

    async def request(self, input: Any = None, *, wait: bool | float | None = None) -> AgentRequestResult:
        return await self._agents.request(self.id, input, wait=wait)

    async def message(self, message: Any) -> AgentMessageResult:
        return await self._agents.message(self.id, message)

    async def chat(self, message: Any, session_id: str | None = None) -> AgentChatResult:
        return await self._agents.chat(self.id, message, session_id)

    def chat_session(self, session_id: str | None = None) -> AsyncChatSession:
        return AsyncChatSession(self, session_id)

    async def trigger(self) -> AgentTriggerResult:
        return await self._agents.trigger(self.id)

    async def info(self) -> AgentInfoResult:
        return await self._agents.info(self.id)

    async def suspend(self) -> AgentSuspendResult:
        return await self._agents.suspend(self.id)

    async def resume(self, *, auto_wake: bool | None = None) -> AgentSuspendResult:
        return await self._agents.resume(self.id, auto_wake=auto_wake)

    async def update(
        self,
        *,
        config: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
    ) -> Any:
        return await self._agents.update(self.id, config=config, state=state)

    async def cancel_task(self, task_id: str) -> Any:
        return await self._agents.cancel_task(self.id, task_id)

    async def fork(
        self,
        agent_id: str,
        *,
        config: dict[str, Any] | None = None,
        include_timeline: bool | None = None,
        overwrite: bool | None = None,
    ) -> AsyncAgent:
        await self._agents.fork(
            self.id,
            agent_id,
            config=config,
            include_timeline=include_timeline,
            overwrite=overwrite,
        )
        return AsyncAgent(agent_id, self.venue)

    async def context(self, task: Any = None) -> str:
        return await self._agents.context(self.id, task)

    async def delete(self, *, remove: bool | None = None) -> AgentDeleteResult:
        return await self._agents.delete(self.id, remove=remove)

    def __repr__(self) -> str:
        return f"AsyncAgent(id={self.id!r})"


class AsyncChatSession:
    """Async mirror of :class:`ChatSession`."""

    def __init__(self, agent: AsyncAgent, session_id: str | None = None) -> None:
        self.agent = agent
        self._session_id = session_id

    @property
    def session_id(self) -> str | None:
        return self._session_id

    async def send(self, message: Any) -> AgentChatResult:
        result = await self.agent.chat(message, self._session_id)
        self._session_id = result.sessionId
        return result
