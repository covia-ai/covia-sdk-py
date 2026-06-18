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


# --- 0.2.x venue output shapes (covia#132): models must parse these without
#     raising, and expose the new fields. The tests above cover pre-0.2.x. ---


def test_read_0_2_x_value_bytes(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"exists": True, "value": {"x": 1}, "valueBytes": 42}),
        status_code=201,
    )
    result = venue.workspace.read("/foo")
    assert result.exists is True
    assert result.valueBytes == 42
    assert result.truncated is None


def test_write_0_2_x_empty(httpx_mock, venue):
    # Overwrite into existing structure → empty object; must not raise.
    httpx_mock.add_response(url=f"{API_BASE}invoke", json=_complete({}), status_code=201)
    result = venue.workspace.write("/foo", 1)
    assert result.pathCreated is None


def test_write_0_2_x_path_created(httpx_mock, venue):
    httpx_mock.add_response(url=f"{API_BASE}invoke", json=_complete({"pathCreated": True}), status_code=201)
    result = venue.workspace.write("/foo/bar/baz", 1)
    assert result.pathCreated is True


def test_delete_0_2_x_empty(httpx_mock, venue):
    httpx_mock.add_response(url=f"{API_BASE}invoke", json=_complete({}), status_code=201)
    result = venue.workspace.delete("/foo")  # must not raise (empty object)
    assert result.deleted is None


def test_append_0_2_x_new_size(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"newSize": 3, "pathCreated": True}),
        status_code=201,
    )
    result = venue.workspace.append("/foo/items", "x")
    assert result.newSize == 3
    assert result.pathCreated is True


def test_list_0_2_x_total_size(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"exists": True, "type": "Map", "totalSize": 2, "offset": 0, "keys": ["a", "b"]}),
        status_code=201,
    )
    result = venue.workspace.list("/foo")
    assert result.totalSize == 2
    assert result.keys == ["a", "b"]


def test_slice_0_2_x_total_size(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"exists": True, "type": "Vector", "values": [1, 2], "totalSize": 2, "offset": 0}),
        status_code=201,
    )
    result = venue.workspace.slice("/foo", offset=0, limit=2)
    assert result.values == [1, 2]
    assert result.totalSize == 2


def test_slice_0_2_x_absent_path(httpx_mock, venue):
    # Absent path returns just {exists: false}; the pre-0.2.x required-field
    # model raised here — the tolerant model must not.
    httpx_mock.add_response(url=f"{API_BASE}invoke", json=_complete({"exists": False}), status_code=201)
    result = venue.workspace.slice("/missing")
    assert result.exists is False


def test_lazy_manager_is_cached(venue):
    assert venue.workspace is venue.workspace
