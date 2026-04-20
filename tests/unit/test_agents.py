"""Tests for AgentManager."""

from __future__ import annotations

from covia import AgentListResult
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


def test_query(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"agentId": "agent-a", "status": "RUNNING", "tasks": []}),
        status_code=201,
    )
    result = venue.agents.query("agent-a")
    assert result.status == "RUNNING"


def test_list(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"agents": [{"agentId": "a", "status": "RUNNING", "tasks": 2}]}),
        status_code=201,
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


def test_lazy_manager_is_cached(venue):
    # accessing venue.agents twice should return the same instance (lazy cache)
    assert venue.agents is venue.agents
