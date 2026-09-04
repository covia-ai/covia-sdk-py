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
    AgentCancelTaskResult,
    AgentChatResult,
    AgentCompactSessionResult,
    AgentCompleteTaskResult,
    AgentCreateResult,
    AgentDeleteResult,
    AgentDeleteSessionResult,
    AgentFailTaskResult,
    AgentForkResult,
    AgentInfoResult,
    AgentListResult,
    AgentMessageResult,
    AgentReloadContextResult,
    AgentRenameSessionResult,
    AgentRequestResult,
    AgentSessionReadResult,
    AgentSessionsResult,
    AgentSuspendResult,
    AgentTriggerResult,
)

if TYPE_CHECKING:
    from covia.async_api.venue import AsyncVenue
    from covia.venue import Venue

_AgentConfig = dict[str, Any] | str | list[Any]


class _SyncInvoker(Protocol):
    def run(self, operation: str, input: Any = None, *, timeout: float | None = None) -> Any: ...
    def _get_agents(self, suffix: str, params: dict[str, Any]) -> dict[str, Any]: ...


class _AsyncInvoker(Protocol):
    async def run(self, operation: str, input: Any = None, *, timeout: float | None = None) -> Any: ...
    async def _get_agents(self, suffix: str, params: dict[str, Any]) -> dict[str, Any]: ...


def _drop_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _agent_request_timeout(wait: bool | float | None, timeout: float | None) -> int | None:
    """Translate the legacy seconds-based ``wait`` option to 0.9.8's
    millisecond ``timeout`` field."""
    if wait is not None and timeout is not None:
        raise ValueError("Pass either wait or timeout, not both")
    value: bool | float | None = timeout if timeout is not None else wait
    if value is None or value is True:
        return None
    if value is False:
        return 0
    if value < 0:
        raise ValueError("timeout must be non-negative")
    return int(value * 1000)


def _agent_http_timeout(timeout_ms: int | None) -> float | None:
    """Leave enough transport time to receive the operation's timeout snapshot."""
    return None if timeout_ms is None else timeout_ms / 1000 + 5


def _normalise_agent_list(data: Any) -> Any:
    """Accept both full entries and the compact agent-id list served by GET."""
    if isinstance(data, list):
        data = {"agents": data}
    if not isinstance(data, dict) or not isinstance(data.get("agents"), list):
        return data
    return {
        **data,
        "agents": [({"agentId": entry} if isinstance(entry, str) else entry) for entry in data["agents"]],
    }


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
        definition: str | None = None,
        config: _AgentConfig | None = None,
    ) -> AgentCreateResult:
        """Create an agent with an optional definition or layered config.

        Covia 0.9.8 requires explicit delete-then-create when replacing an
        agent; resolved config composition supplies any initial state.
        """
        payload = _drop_none(
            {
                "agentId": agent_id,
                "definition": definition,
                "config": config,
            }
        )
        return AgentCreateResult.model_validate(self._venue.run("v/ops/agent/create", payload))

    def request(
        self,
        agent_id: str,
        input: dict[str, Any],
        *,
        wait: bool | float | None = None,
        timeout: float | None = None,
        session_id: str | None = None,
        response_schema: dict[str, Any] | None = None,
        strict: bool | None = None,
        output_path: str | None = None,
        loads: dict[str, Any] | None = None,
    ) -> AgentRequestResult:
        """Send a request to an agent.

        Args:
            agent_id: Target agent id.
            input: Request payload (shape is agent-specific).
            wait: Backward-compatible alias for ``timeout``. Numeric values
                are seconds; ``False`` requests immediate submission.
            timeout: Maximum seconds to wait for an answer.
            session_id: Optional conversation session to continue.
            response_schema: Optional JSON Schema for structured output.
            strict: Require output to conform to ``response_schema``.
            output_path: Optional workspace destination for the response.
            loads: Optional session context entries keyed by source name.
        """
        timeout_ms = _agent_request_timeout(wait, timeout)
        payload = _drop_none(
            {
                "agentId": agent_id,
                "input": input,
                "timeout": timeout_ms,
                "sessionId": session_id,
                "responseSchema": response_schema,
                "strict": strict,
                "outputPath": output_path,
                "loads": loads,
            }
        )
        return AgentRequestResult.model_validate(
            self._venue.run("v/ops/agent/request", payload, timeout=_agent_http_timeout(timeout_ms))
        )

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
        *,
        loads: dict[str, Any] | None = None,
    ) -> AgentChatResult:
        """Send a message to an agent and block for its next response on the session.

        Session lifecycle:

        * Omit ``session_id`` on the first call — the server mints a session
          and returns its id in :attr:`AgentChatResult.sessionId`. Capture it.
        * Pass the returned ``session_id`` on every subsequent call to continue
          the conversation.
        * An unknown ``session_id`` is rejected (the server will not silently
          mint one); omit the argument to start a new session.

        Calls on the same session may run concurrently; each response reports
        which message ids it answered in :attr:`AgentChatResult.answered`.
        """
        payload = _drop_none({"agentId": agent_id, "message": message, "sessionId": session_id, "loads": loads})
        return AgentChatResult.model_validate(self._venue.run("v/ops/agent/chat", payload))

    def trigger(self, agent_id: str) -> AgentTriggerResult:
        """Fire any pending scheduled work for an agent."""
        return AgentTriggerResult.model_validate(self._venue.run("v/ops/agent/trigger", {"agentId": agent_id}))

    def info(self, agent_id: str) -> AgentInfoResult:
        """A lightweight status/config summary for an agent.

        **Job-free** on covia ≥ 0.4 (``GET /api/v1/agents/{id}``, covia #180);
        older venues transparently fall back to the operation path (one probe,
        remembered)."""
        data = self._agents_get(f"/{agent_id}", {}, lambda: self._venue.run("v/ops/agent/info", {"agentId": agent_id}))
        return AgentInfoResult.model_validate(data)

    def list(self, *, include_terminated: bool | None = None) -> AgentListResult:
        """List agents on this venue.

        **Job-free** on covia ≥ 0.4 (``GET /api/v1/agents``, covia #180);
        older venues transparently fall back to the operation path."""
        params = _drop_none({"includeTerminated": include_terminated})
        data = self._agents_get("", params, lambda: self._venue.run("v/ops/agent/list", params))
        return AgentListResult.model_validate(_normalise_agent_list(data))

    def _agents_get(self, suffix: str, params: dict[str, Any], fallback: Any) -> Any:
        """A job-free agents GET, falling back to the operation path on pre-0.4
        venues — the GET surface 404s there, and only there (an unknown agent
        id is a structured error, not a bare 404). The probe result is
        remembered so old venues pay it once."""
        if self._agents_get_supported:
            try:
                return self._venue._get_agents(suffix, params)
            except NotFoundError:
                if suffix:
                    raise
                self._agents_get_supported = False
            except GridError as exc:
                if exc.status_code != 404:
                    raise
                if suffix:
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
        config: _AgentConfig | None = None,
        state: dict[str, Any] | None = None,
    ) -> Any:
        """Update an agent's config and/or state."""
        payload = _drop_none({"agentId": agent_id, "config": config, "state": state})
        return self._venue.run("v/ops/agent/update", payload)

    def cancel_task(
        self,
        agent_id: str,
        task_id: str,
        *,
        reason: str | None = None,
    ) -> AgentCancelTaskResult:
        """Cancel a running task on an agent."""
        return AgentCancelTaskResult.model_validate(
            self._venue.run(
                "v/ops/agent/cancel-task",
                _drop_none({"agentId": agent_id, "taskId": task_id, "reason": reason}),
            )
        )

    def sessions(
        self,
        agent_id: str,
        *,
        offset: int | None = None,
        limit: int | None = None,
    ) -> AgentSessionsResult:
        """List saved chat sessions for an agent."""
        payload = _drop_none({"agentId": agent_id, "offset": offset, "limit": limit})
        return AgentSessionsResult.model_validate(self._venue.run("v/ops/agent/sessions", payload))

    def read_session(
        self,
        agent_id: str,
        session_id: str | None = None,
        *,
        max_turns: int | None = None,
        max_chars: int | None = None,
        archive_depth: int | None = None,
    ) -> AgentSessionReadResult:
        """Read a saved chat session."""
        payload = _drop_none(
            {
                "agentId": agent_id,
                "sessionId": session_id,
                "maxTurns": max_turns,
                "maxChars": max_chars,
                "archiveDepth": archive_depth,
            }
        )
        return AgentSessionReadResult.model_validate(self._venue.run("v/ops/agent/session-read", payload))

    def rename_session(self, agent_id: str, session_id: str, title: str | None = None) -> AgentRenameSessionResult:
        """Rename a saved chat session."""
        payload = _drop_none({"agentId": agent_id, "sessionId": session_id, "title": title})
        return AgentRenameSessionResult.model_validate(self._venue.run("v/ops/agent/rename-session", payload))

    def compact_session(self, agent_id: str, session_id: str, summary: str) -> AgentCompactSessionResult:
        """Compact older turns in a saved chat session."""
        payload = {"agentId": agent_id, "sessionId": session_id, "summary": summary}
        return AgentCompactSessionResult.model_validate(self._venue.run("v/ops/agent/compact-session", payload))

    def reload_context(self, agent_id: str, session_id: str) -> AgentReloadContextResult:
        """Reload a chat session's context frames."""
        payload = {"agentId": agent_id, "sessionId": session_id}
        return AgentReloadContextResult.model_validate(self._venue.run("v/ops/agent/reload-context", payload))

    def delete_session(self, agent_id: str, session_id: str) -> AgentDeleteSessionResult:
        """Delete a saved chat session."""
        payload = {"agentId": agent_id, "sessionId": session_id}
        return AgentDeleteSessionResult.model_validate(self._venue.run("v/ops/agent/delete-session", payload))

    def fork(
        self,
        source_id: str,
        agent_id: str,
        *,
        config: _AgentConfig | None = None,
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
        definition: str | None = None,
        config: _AgentConfig | None = None,
    ) -> AgentCreateResult:
        payload = _drop_none(
            {
                "agentId": agent_id,
                "definition": definition,
                "config": config,
            }
        )
        return AgentCreateResult.model_validate(await self._venue.run("v/ops/agent/create", payload))

    async def request(
        self,
        agent_id: str,
        input: dict[str, Any],
        *,
        wait: bool | float | None = None,
        timeout: float | None = None,
        session_id: str | None = None,
        response_schema: dict[str, Any] | None = None,
        strict: bool | None = None,
        output_path: str | None = None,
        loads: dict[str, Any] | None = None,
    ) -> AgentRequestResult:
        timeout_ms = _agent_request_timeout(wait, timeout)
        payload = _drop_none(
            {
                "agentId": agent_id,
                "input": input,
                "timeout": timeout_ms,
                "sessionId": session_id,
                "responseSchema": response_schema,
                "strict": strict,
                "outputPath": output_path,
                "loads": loads,
            }
        )
        return AgentRequestResult.model_validate(
            await self._venue.run("v/ops/agent/request", payload, timeout=_agent_http_timeout(timeout_ms))
        )

    async def message(self, agent_id: str, message: Any) -> AgentMessageResult:
        return AgentMessageResult.model_validate(
            await self._venue.run("v/ops/agent/message", {"agentId": agent_id, "message": message})
        )

    async def chat(
        self,
        agent_id: str,
        message: Any,
        session_id: str | None = None,
        *,
        loads: dict[str, Any] | None = None,
    ) -> AgentChatResult:
        payload = _drop_none({"agentId": agent_id, "message": message, "sessionId": session_id, "loads": loads})
        return AgentChatResult.model_validate(await self._venue.run("v/ops/agent/chat", payload))

    async def trigger(self, agent_id: str) -> AgentTriggerResult:
        return AgentTriggerResult.model_validate(await self._venue.run("v/ops/agent/trigger", {"agentId": agent_id}))

    async def info(self, agent_id: str) -> AgentInfoResult:
        """A lightweight status/config summary for an agent (job-free on
        covia ≥ 0.4, covia #180; older venues fall back to the operation path)."""
        data = await self._agents_get(
            f"/{agent_id}", {}, lambda: self._venue.run("v/ops/agent/info", {"agentId": agent_id})
        )
        return AgentInfoResult.model_validate(data)

    async def list(self, *, include_terminated: bool | None = None) -> AgentListResult:
        """List agents on this venue (job-free on covia ≥ 0.4, covia #180;
        older venues fall back to the operation path)."""
        params = _drop_none({"includeTerminated": include_terminated})
        data = await self._agents_get("", params, lambda: self._venue.run("v/ops/agent/list", params))
        return AgentListResult.model_validate(_normalise_agent_list(data))

    async def _agents_get(self, suffix: str, params: dict[str, Any], fallback: Any) -> Any:
        """A job-free agents GET, falling back to the operation path on pre-0.4
        venues (404 probe, remembered)."""
        if self._agents_get_supported:
            try:
                return await self._venue._get_agents(suffix, params)
            except NotFoundError:
                if suffix:
                    raise
                self._agents_get_supported = False
            except GridError as exc:
                if exc.status_code != 404:
                    raise
                if suffix:
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
        config: _AgentConfig | None = None,
        state: dict[str, Any] | None = None,
    ) -> Any:
        payload = _drop_none({"agentId": agent_id, "config": config, "state": state})
        return await self._venue.run("v/ops/agent/update", payload)

    async def cancel_task(
        self,
        agent_id: str,
        task_id: str,
        *,
        reason: str | None = None,
    ) -> AgentCancelTaskResult:
        return AgentCancelTaskResult.model_validate(
            await self._venue.run(
                "v/ops/agent/cancel-task",
                _drop_none({"agentId": agent_id, "taskId": task_id, "reason": reason}),
            )
        )

    async def sessions(
        self,
        agent_id: str,
        *,
        offset: int | None = None,
        limit: int | None = None,
    ) -> AgentSessionsResult:
        payload = _drop_none({"agentId": agent_id, "offset": offset, "limit": limit})
        return AgentSessionsResult.model_validate(await self._venue.run("v/ops/agent/sessions", payload))

    async def read_session(
        self,
        agent_id: str,
        session_id: str | None = None,
        *,
        max_turns: int | None = None,
        max_chars: int | None = None,
        archive_depth: int | None = None,
    ) -> AgentSessionReadResult:
        payload = _drop_none(
            {
                "agentId": agent_id,
                "sessionId": session_id,
                "maxTurns": max_turns,
                "maxChars": max_chars,
                "archiveDepth": archive_depth,
            }
        )
        return AgentSessionReadResult.model_validate(await self._venue.run("v/ops/agent/session-read", payload))

    async def rename_session(
        self, agent_id: str, session_id: str, title: str | None = None
    ) -> AgentRenameSessionResult:
        payload = _drop_none({"agentId": agent_id, "sessionId": session_id, "title": title})
        return AgentRenameSessionResult.model_validate(await self._venue.run("v/ops/agent/rename-session", payload))

    async def compact_session(self, agent_id: str, session_id: str, summary: str) -> AgentCompactSessionResult:
        payload = {"agentId": agent_id, "sessionId": session_id, "summary": summary}
        return AgentCompactSessionResult.model_validate(await self._venue.run("v/ops/agent/compact-session", payload))

    async def reload_context(self, agent_id: str, session_id: str) -> AgentReloadContextResult:
        payload = {"agentId": agent_id, "sessionId": session_id}
        return AgentReloadContextResult.model_validate(await self._venue.run("v/ops/agent/reload-context", payload))

    async def delete_session(self, agent_id: str, session_id: str) -> AgentDeleteSessionResult:
        payload = {"agentId": agent_id, "sessionId": session_id}
        return AgentDeleteSessionResult.model_validate(await self._venue.run("v/ops/agent/delete-session", payload))

    async def fork(
        self,
        source_id: str,
        agent_id: str,
        *,
        config: _AgentConfig | None = None,
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

    def request(
        self,
        input: dict[str, Any],
        *,
        wait: bool | float | None = None,
        timeout: float | None = None,
        session_id: str | None = None,
        response_schema: dict[str, Any] | None = None,
        strict: bool | None = None,
        output_path: str | None = None,
        loads: dict[str, Any] | None = None,
    ) -> AgentRequestResult:
        """Send a request to this agent (see :meth:`AgentManager.request`)."""
        options = _drop_none(
            {
                "wait": wait,
                "timeout": timeout,
                "session_id": session_id,
                "response_schema": response_schema,
                "strict": strict,
                "output_path": output_path,
                "loads": loads,
            }
        )
        return self._agents.request(self.id, input, **options)

    def message(self, message: Any) -> AgentMessageResult:
        """Deliver a fire-and-forget message to this agent."""
        return self._agents.message(self.id, message)

    def chat(
        self,
        message: Any,
        session_id: str | None = None,
        *,
        loads: dict[str, Any] | None = None,
    ) -> AgentChatResult:
        """Send a message and block for this agent's next response on the session."""
        return (
            self._agents.chat(self.id, message, session_id, loads=loads)
            if loads is not None
            else self._agents.chat(self.id, message, session_id)
        )

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
        config: _AgentConfig | None = None,
        state: dict[str, Any] | None = None,
    ) -> Any:
        """Update this agent's config and/or state."""
        return self._agents.update(self.id, config=config, state=state)

    def cancel_task(self, task_id: str, *, reason: str | None = None) -> AgentCancelTaskResult:
        """Cancel a running task on this agent."""
        return (
            self._agents.cancel_task(self.id, task_id, reason=reason)
            if reason is not None
            else self._agents.cancel_task(self.id, task_id)
        )

    def sessions(self, *, offset: int | None = None, limit: int | None = None) -> AgentSessionsResult:
        """List this agent's saved chat sessions."""
        return self._agents.sessions(self.id, offset=offset, limit=limit)

    def read_session(
        self,
        session_id: str | None = None,
        *,
        max_turns: int | None = None,
        max_chars: int | None = None,
        archive_depth: int | None = None,
    ) -> AgentSessionReadResult:
        """Read one of this agent's saved chat sessions."""
        return self._agents.read_session(
            self.id,
            session_id,
            max_turns=max_turns,
            max_chars=max_chars,
            archive_depth=archive_depth,
        )

    def fork(
        self,
        agent_id: str,
        *,
        config: _AgentConfig | None = None,
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

    def send(self, message: Any, *, loads: dict[str, Any] | None = None) -> AgentChatResult:
        """Send *message* on this session, capturing the session id from the reply."""
        result = self.agent.chat(message, self._session_id, loads=loads)
        self._session_id = result.sessionId
        return result

    def read(
        self,
        *,
        max_turns: int | None = None,
        max_chars: int | None = None,
        archive_depth: int | None = None,
    ) -> AgentSessionReadResult:
        """Read this session's saved messages."""
        return self.agent.read_session(
            self._require_session_id(),
            max_turns=max_turns,
            max_chars=max_chars,
            archive_depth=archive_depth,
        )

    def rename(self, title: str | None = None) -> AgentRenameSessionResult:
        """Rename this session."""
        return self.agent._agents.rename_session(self.agent.id, self._require_session_id(), title)

    def compact(self, summary: str) -> AgentCompactSessionResult:
        """Compact older turns in this session."""
        return self.agent._agents.compact_session(self.agent.id, self._require_session_id(), summary)

    def reload_context(self) -> AgentReloadContextResult:
        """Reload this session's context frames."""
        return self.agent._agents.reload_context(self.agent.id, self._require_session_id())

    def delete(self) -> AgentDeleteSessionResult:
        """Delete this saved session."""
        return self.agent._agents.delete_session(self.agent.id, self._require_session_id())

    def _require_session_id(self) -> str:
        if self._session_id is None:
            raise ValueError("The session has no id; send a message first")
        return self._session_id


class AsyncAgent:
    """Async mirror of :class:`Agent`. Obtained via
    :meth:`AsyncVenue.agent <covia.async_api.venue.AsyncVenue.agent>`."""

    def __init__(self, agent_id: str, venue: AsyncVenue) -> None:
        self.id = agent_id
        self.venue = venue
        self._agents: AsyncAgentManager = venue.agents

    async def request(
        self,
        input: dict[str, Any],
        *,
        wait: bool | float | None = None,
        timeout: float | None = None,
        session_id: str | None = None,
        response_schema: dict[str, Any] | None = None,
        strict: bool | None = None,
        output_path: str | None = None,
        loads: dict[str, Any] | None = None,
    ) -> AgentRequestResult:
        options = _drop_none(
            {
                "wait": wait,
                "timeout": timeout,
                "session_id": session_id,
                "response_schema": response_schema,
                "strict": strict,
                "output_path": output_path,
                "loads": loads,
            }
        )
        return await self._agents.request(self.id, input, **options)

    async def message(self, message: Any) -> AgentMessageResult:
        return await self._agents.message(self.id, message)

    async def chat(
        self,
        message: Any,
        session_id: str | None = None,
        *,
        loads: dict[str, Any] | None = None,
    ) -> AgentChatResult:
        if loads is None:
            return await self._agents.chat(self.id, message, session_id)
        return await self._agents.chat(self.id, message, session_id, loads=loads)

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
        config: _AgentConfig | None = None,
        state: dict[str, Any] | None = None,
    ) -> Any:
        return await self._agents.update(self.id, config=config, state=state)

    async def cancel_task(self, task_id: str, *, reason: str | None = None) -> AgentCancelTaskResult:
        if reason is None:
            return await self._agents.cancel_task(self.id, task_id)
        return await self._agents.cancel_task(self.id, task_id, reason=reason)

    async def sessions(self, *, offset: int | None = None, limit: int | None = None) -> AgentSessionsResult:
        return await self._agents.sessions(self.id, offset=offset, limit=limit)

    async def read_session(
        self,
        session_id: str | None = None,
        *,
        max_turns: int | None = None,
        max_chars: int | None = None,
        archive_depth: int | None = None,
    ) -> AgentSessionReadResult:
        return await self._agents.read_session(
            self.id,
            session_id,
            max_turns=max_turns,
            max_chars=max_chars,
            archive_depth=archive_depth,
        )

    async def fork(
        self,
        agent_id: str,
        *,
        config: _AgentConfig | None = None,
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

    async def send(self, message: Any, *, loads: dict[str, Any] | None = None) -> AgentChatResult:
        result = await self.agent.chat(message, self._session_id, loads=loads)
        self._session_id = result.sessionId
        return result

    async def read(
        self,
        *,
        max_turns: int | None = None,
        max_chars: int | None = None,
        archive_depth: int | None = None,
    ) -> AgentSessionReadResult:
        return await self.agent.read_session(
            self._require_session_id(),
            max_turns=max_turns,
            max_chars=max_chars,
            archive_depth=archive_depth,
        )

    async def rename(self, title: str | None = None) -> AgentRenameSessionResult:
        return await self.agent._agents.rename_session(self.agent.id, self._require_session_id(), title)

    async def compact(self, summary: str) -> AgentCompactSessionResult:
        return await self.agent._agents.compact_session(self.agent.id, self._require_session_id(), summary)

    async def reload_context(self) -> AgentReloadContextResult:
        return await self.agent._agents.reload_context(self.agent.id, self._require_session_id())

    async def delete(self) -> AgentDeleteSessionResult:
        return await self.agent._agents.delete_session(self.agent.id, self._require_session_id())

    def _require_session_id(self) -> str:
        if self._session_id is None:
            raise ValueError("The session has no id; send a message first")
        return self._session_id
