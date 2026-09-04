"""Tests for SecretManager and raw Venue secret REST endpoints."""

from __future__ import annotations

from tests.conftest import VENUE_URL

API_BASE = f"{VENUE_URL}/api/v1/"


def _complete(output: object) -> object:
    return output


def test_list(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}secrets",
        json={"items": ["API_KEY", "DB_PASSWORD"], "total": 2},
    )
    assert venue.secrets.list() == ["API_KEY", "DB_PASSWORD"]


def test_delete(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}secrets/API_KEY",
        method="DELETE",
        text="",
    )
    venue.secrets.delete("API_KEY")


def test_set_via_op(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}run",
        json=_complete({"name": "API_KEY", "stored": True}),
        status_code=201,
    )
    result = venue.secrets.set("API_KEY", "s3cret")
    assert result.stored is True
    import json

    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert body["operation"] == "v/ops/secret/set"
    assert body["input"] == {"name": "API_KEY", "value": "s3cret", "overwrite": False}


def test_set_can_explicitly_overwrite(httpx_mock, venue):
    import json

    httpx_mock.add_response(url=f"{API_BASE}run", json={"name": "API_KEY", "stored": True})
    venue.secrets.set("API_KEY", "replacement", overwrite=True)
    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert body["input"]["overwrite"] is True


def test_extract_via_op(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}run",
        json=_complete({"name": "API_KEY", "value": "s3cret"}),
        status_code=201,
    )
    result = venue.secrets.extract("API_KEY")
    assert result.value == "s3cret"


def test_extract_forwards_ucans(httpx_mock, venue):
    # extract requires a capability grant — the proof must reach the envelope.
    import json

    httpx_mock.add_response(
        url=f"{API_BASE}run",
        json=_complete({"name": "API_KEY", "value": "s3cret"}),
        status_code=201,
    )
    venue.secrets.extract("API_KEY", ucans=["eyJ.grant"])
    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert body["operation"] == "v/ops/secret/extract"
    assert body["ucans"] == ["eyJ.grant"]


def test_raw_venue_helpers(httpx_mock, venue):
    # Exercise the REST shim on Venue directly.
    httpx_mock.add_response(
        url=f"{API_BASE}secrets",
        json={"items": [], "total": 0},
    )
    assert venue.list_secrets() == []


def test_lazy_manager_is_cached(venue):
    assert venue.secrets is venue.secrets
