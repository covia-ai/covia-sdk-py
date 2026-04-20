"""Tests for WorkspaceManager."""

from __future__ import annotations

import json

from tests.conftest import VENUE_URL

API_BASE = f"{VENUE_URL}/api/v1/"


def _complete(output: object) -> dict[str, object]:
    return {"id": "job-ws", "status": "COMPLETE", "output": output}


def test_read(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"exists": True, "value": {"x": 1}, "size": 42}),
        status_code=201,
    )
    result = venue.workspace.read("/foo/bar")
    assert result.exists is True
    assert result.value == {"x": 1}
    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert body["operation"] == "v/ops/covia/read"
    assert body["input"] == {"path": "/foo/bar"}


def test_read_with_max_size(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"exists": True, "value": "short", "truncated": False}),
        status_code=201,
    )
    venue.workspace.read("/foo", max_size=100)
    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert body["input"] == {"path": "/foo", "maxSize": 100}


def test_write(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"written": True}),
        status_code=201,
    )
    result = venue.workspace.write("/foo", {"y": 2})
    assert result.written is True


def test_delete(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"deleted": True}),
        status_code=201,
    )
    result = venue.workspace.delete("/foo")
    assert result.deleted is True


def test_append(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"appended": True}),
        status_code=201,
    )
    result = venue.workspace.append("/foo", "new-entry")
    assert result.appended is True


def test_list(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"exists": True, "type": "map", "count": 2, "keys": ["a", "b"]}),
        status_code=201,
    )
    result = venue.workspace.list("/foo", limit=10)
    assert result.count == 2
    assert result.keys == ["a", "b"]


def test_slice(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"exists": True, "type": "list", "values": [1, 2], "count": 2, "offset": 0}),
        status_code=201,
    )
    result = venue.workspace.slice("/foo", offset=0, limit=2)
    assert result.values == [1, 2]


def test_lazy_manager_is_cached(venue):
    assert venue.workspace is venue.workspace
