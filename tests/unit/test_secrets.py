"""Tests for SecretManager and raw Venue secret REST endpoints."""

from __future__ import annotations

from tests.conftest import VENUE_URL

API_BASE = f"{VENUE_URL}/api/v1/"


def _complete(output: object) -> dict[str, object]:
    return {"id": "job-secret", "status": "COMPLETE", "output": output}


def test_list(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}secrets",
        json={"items": ["API_KEY", "DB_PASSWORD"], "total": 2},
    )
    assert venue.secrets.list() == ["API_KEY", "DB_PASSWORD"]


def test_put(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}secrets/API_KEY",
        method="PUT",
        text="",
    )
    venue.secrets.put("API_KEY", "s3cret")
    req = httpx_mock.get_requests()[-1]
    import json

    assert json.loads(req.content) == {"value": "s3cret"}


def test_delete(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}secrets/API_KEY",
        method="DELETE",
        text="",
    )
    venue.secrets.delete("API_KEY")


def test_set_via_op(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"name": "API_KEY", "stored": True}),
        status_code=201,
    )
    result = venue.secrets.set("API_KEY", "s3cret")
    assert result.stored is True
    import json

    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert body["operation"] == "v/ops/secret/set"


def test_extract_via_op(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_complete({"name": "API_KEY", "value": "s3cret"}),
        status_code=201,
    )
    result = venue.secrets.extract("API_KEY")
    assert result.value == "s3cret"


def test_raw_venue_helpers(httpx_mock, venue):
    # Exercise the REST shim on Venue directly.
    httpx_mock.add_response(
        url=f"{API_BASE}secrets",
        json={"items": [], "total": 0},
    )
    assert venue.list_secrets() == []


def test_lazy_manager_is_cached(venue):
    assert venue.secrets is venue.secrets
