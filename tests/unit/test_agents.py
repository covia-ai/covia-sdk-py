"""Tests for AgentManager, the Agent handle, and ChatSession."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from covia import Agent, AgentListResult
from covia.agents import AsyncAgent
from covia.models import AgentChatResult
from tests.conftest import VENUE_URL

API_BASE = f"{VENUE_URL}/api/v1/"


def _complete(output: object) -> dict[str, object]:
    return {"id": "job-agent", "status": "COMPLETE", "output": output}


def test_create(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"agentId": "agent-a", "status": "CREATED", "created": True}),
        status_code=201,
    )
    result = venue.agents.create("agent-a", config={"role": "assistant"})
    assert result.agentId == "agent-a"
    assert result.created is True
    # Verify wire payload sent camelCase + drops None fields
    sent = httpx_mock.get_requests()[-1]
    import json

    body = json.loads(sent.content)
    assert body["operation"] == "v/ops/agent/create"
    assert body["input"] == {"agentId": "agent-a", "config": {"role": "assistant"}}


def test_request(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"id": "req-1", "status": "DONE", "output": {"answer": 42}}),
        status_code=201,
    )
    result = venue.agents.request("agent-a", {"q": "hello"}, wait=5)
    assert result.id == "req-1"
    assert result.output == {"answer": 42}


def test_request_tolerates_bare_result(httpx_mock, venue):
    # A synchronously-awaited agent that returns a bare result (no id/status
    # envelope) must still validate — id/status are optional.
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"answer": 42}),
        status_code=201,
    )
    result = venue.agents.request("agent-a", {"q": "hello"}, wait=5)
    assert result.id is None
    assert result.status is None
    assert result.model_dump()["answer"] == 42


def test_message(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"agentId": "agent-a", "delivered": True}),
        status_code=201,
    )
    result = venue.agents.message("agent-a", {"text": "hi"})
    assert result.delivered is True


def test_chat_first_call_omits_session_id(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"agentId": "agent-a", "sessionId": "sess-123", "response": "hello!"}),
        status_code=201,
    )
    result = venue.agents.chat("agent-a", "hi")
    assert result.sessionId == "sess-123"
    assert result.response == "hello!"
    import json

    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert "sessionId" not in body["input"], "first chat call must not send sessionId"


def test_chat_continues_session(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"agentId": "agent-a", "sessionId": "sess-123", "response": "still here"}),
        status_code=201,
    )
    result = venue.agents.chat("agent-a", "follow up", session_id="sess-123")
    assert result.sessionId == "sess-123"
    import json

    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert body["input"]["sessionId"] == "sess-123"


def test_info(httpx_mock, venue):
    # Job-free on covia >= 0.4: GET /api/v1/agents/{id} (covia #180).
    httpx_mock.add_response(
        url=f"{API_BASE}agents/agent-a",
        json={"agentId": "agent-a", "status": "RUNNING", "timelineLength": 3, "tasks": 1},
    )
    result = venue.agents.info("agent-a")
    assert result.agentId == "agent-a"
    assert result.status == "RUNNING"
    assert result.timelineLength == 3
    assert result.tasks == 1
    sent = httpx_mock.get_requests()[-1]
    assert sent.method == "GET"  # job-free — no invoke, no job
    assert str(sent.url).endswith("/api/v1/agents/agent-a")


def test_list(httpx_mock, venue):
    # Job-free on covia >= 0.4: GET /api/v1/agents (covia #180).
    httpx_mock.add_response(
        url=f"{API_BASE}agents",
        json={"agents": [{"agentId": "a", "status": "RUNNING", "tasks": 2}]},
    )
    result = venue.agents.list()
    assert isinstance(result, AgentListResult)
    assert len(result.agents) == 1
    assert result.agents[0].tasks == 2


def test_delete(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"agentId": "agent-a", "status": "DELETED", "removed": True}),
        status_code=201,
    )
    result = venue.agents.delete("agent-a", remove=True)
    assert result.removed is True


def test_suspend_resume(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"agentId": "agent-a", "status": "SUSPENDED"}),
        status_code=201,
    )
    assert venue.agents.suspend("agent-a").status == "SUSPENDED"

    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"agentId": "agent-a", "status": "RUNNING"}),
        status_code=201,
    )
    assert venue.agents.resume("agent-a", auto_wake=True).status == "RUNNING"


def test_trigger(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"agentId": "agent-a", "status": "TRIGGERED", "result": None}),
        status_code=201,
    )
    result = venue.agents.trigger("agent-a")
    assert result.status == "TRIGGERED"


def test_fork(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"agentId": "agent-b", "status": "CREATED", "created": True, "forkedFrom": "agent-a"}),
        status_code=201,
    )
    result = venue.agents.fork("agent-a", "agent-b", include_timeline=True)
    assert result.agentId == "agent-b"
    assert result.forkedFrom == "agent-a"
    import json

    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert body["operation"] == "v/ops/agent/fork"
    assert body["input"] == {"sourceId": "agent-a", "agentId": "agent-b", "includeTimeline": True}


def test_context(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete("rendered context"),
        status_code=201,
    )
    result = venue.agents.context("agent-a", {"goal": "test"})
    assert result == "rendered context"
    import json

    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert body["operation"] == "v/ops/agent/context"
    assert body["input"] == {"agentId": "agent-a", "task": {"goal": "test"}}


def test_complete_task(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"agentId": "agent-a", "taskId": "task-1", "status": "COMPLETE"}),
        status_code=201,
    )
    result = venue.agents.complete_task({"answer": 42})
    assert result.status == "COMPLETE"
    import json

    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert body["operation"] == "v/ops/agent/complete-task"
    assert body["input"] == {"result": {"answer": 42}}


def test_fail_task(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"agentId": "agent-a", "taskId": "task-1", "status": "FAILED"}),
        status_code=201,
    )
    result = venue.agents.fail_task("boom")
    assert result.status == "FAILED"
    import json

    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert body["operation"] == "v/ops/agent/fail-task"
    assert body["input"] == {"error": "boom"}


def test_lazy_manager_is_cached(venue):
    # accessing venue.agents twice should return the same instance (lazy cache)
    assert venue.agents is venue.agents


# ---------------------------------------------------------------------------
# Agent handle + ChatSession (delegation to the manager)
# ---------------------------------------------------------------------------


def _handle_with_mock() -> tuple[Agent, MagicMock, MagicMock]:
    agents = MagicMock()
    venue = MagicMock()
    venue.agents = agents
    return Agent("a1", venue), agents, venue


def test_venue_agent_returns_handle(venue):
    handle = venue.agent("a1")
    assert isinstance(handle, Agent)
    assert handle.id == "a1"
    assert handle.venue is venue


def test_agent_request_delegates():
    agent, agents, _ = _handle_with_mock()
    agent.request({"q": "hi"}, wait=True)
    agents.request.assert_called_once_with("a1", {"q": "hi"}, wait=True)


def test_agent_chat_delegates():
    agent, agents, _ = _handle_with_mock()
    agent.chat("hello", "sess-1")
    agents.chat.assert_called_once_with("a1", "hello", "sess-1")


def test_agent_update_binds_id():
    agent, agents, _ = _handle_with_mock()
    agent.update(config={"op": "x"}, state={"n": 1})
    agents.update.assert_called_once_with("a1", config={"op": "x"}, state={"n": 1})


def test_agent_info_suspend_resume_delete_context_delegate():
    agent, agents, _ = _handle_with_mock()
    agent.info()
    agents.info.assert_called_once_with("a1")
    agent.suspend()
    agents.suspend.assert_called_once_with("a1")
    agent.resume(auto_wake=True)
    agents.resume.assert_called_once_with("a1", auto_wake=True)
    agent.cancel_task("t-1")
    agents.cancel_task.assert_called_once_with("a1", "t-1")
    agent.context({"goal": "g"})
    agents.context.assert_called_once_with("a1", {"goal": "g"})
    agent.delete(remove=True)
    agents.delete.assert_called_once_with("a1", remove=True)


def test_agent_fork_returns_new_handle():
    agent, agents, venue = _handle_with_mock()
    forked = agent.fork("a2", include_timeline=True)
    agents.fork.assert_called_once_with("a1", "a2", config=None, include_timeline=True, overwrite=None)
    assert isinstance(forked, Agent)
    assert forked.id == "a2"
    assert forked.venue is venue


def test_chat_session_captures_session_id():
    agent, agents, _ = _handle_with_mock()
    agents.chat.return_value = AgentChatResult(agentId="a1", sessionId="sess-1", response="hi")
    session = agent.chat_session()
    assert session.session_id is None
    result = session.send("hello")
    agents.chat.assert_called_once_with("a1", "hello", None)
    assert session.session_id == "sess-1"
    assert result.sessionId == "sess-1"


def test_chat_session_resumes_and_reuses_id():
    agent, agents, _ = _handle_with_mock()
    agents.chat.return_value = AgentChatResult(agentId="a1", sessionId="sess-9", response="ok")
    session = agent.chat_session("sess-9")
    assert session.session_id == "sess-9"
    session.send("continue")
    agents.chat.assert_called_once_with("a1", "continue", "sess-9")


async def test_async_agent_delegates_and_chat_session():
    agents = AsyncMock()
    venue = MagicMock()
    venue.agents = agents
    agent = AsyncAgent("a1", venue)

    await agent.info()
    agents.info.assert_awaited_once_with("a1")

    agents.chat.return_value = AgentChatResult(agentId="a1", sessionId="sess-2", response="hi")
    session = agent.chat_session()
    result = await session.send("hello")
    agents.chat.assert_awaited_once_with("a1", "hello", None)
    assert session.session_id == "sess-2"
    assert result.sessionId == "sess-2"
