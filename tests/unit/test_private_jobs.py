"""Tests for private ``/run`` calls (covia 0.9.8) and UCAN verification."""

from __future__ import annotations

import json

import pytest

from covia.exceptions import CoviaError
from tests.conftest import VENUE_URL

API_BASE = f"{VENUE_URL}/api/v1/"


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


def test_private_run_single_request_no_polling(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}run",
        json={"echo": "hi"},
        status_code=200,
    )
    venue.set_private(True)
    result = venue.run("v/test/ops/echo", {"echo": "hi"})
    assert result == {"echo": "hi"}

    requests = httpx_mock.get_requests()
    assert len(requests) == 1, "private run must use one result-oriented request"
    body = json.loads(requests[0].content)
    assert body["private"] is True
    assert "wait" not in body


def test_private_run_timeout_is_not_a_wire_field(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}run",
        json=42,
        status_code=200,
    )
    venue.set_private(True)
    assert venue.run("v/test/ops/echo", {}, timeout=5.0) == 42
    body = json.loads(httpx_mock.get_requests()[0].content)
    assert "wait" not in body


def test_per_call_private_does_not_change_connection_mode(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}run",
        json="done",
        status_code=200,
    )
    assert venue.run("v/test/ops/echo", {}, private=True) == "done"
    assert json.loads(httpx_mock.get_requests()[0].content)["private"] is True
    assert venue._private is False


def test_per_call_non_private_overrides_connection_mode(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}run",
        json="done",
        status_code=200,
    )
    venue.set_private(True)
    assert venue.run("v/test/ops/echo", {}, private=False) == "done"
    assert "private" not in json.loads(httpx_mock.get_requests()[0].content)


def test_private_invoke_raises_without_request(httpx_mock, venue):
    venue.set_private(True)
    with pytest.raises(CoviaError, match="run\\(\\)"):
        venue.invoke("v/test/ops/echo", {})
    assert len(httpx_mock.get_requests()) == 0, "must fail before any HTTP request"


def test_set_private_false_restores_normal_invoke(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json={"id": "job-private", "status": "PENDING"},
        status_code=201,
    )
    venue.set_private(True)
    venue.set_private(False)
    job = venue.invoke("v/test/ops/echo", {})
    assert job.id == "job-private"
    body = json.loads(httpx_mock.get_requests()[0].content)
    assert "private" not in body
    assert "wait" not in body


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


async def test_async_private_run_single_request(httpx_mock, async_venue):
    httpx_mock.add_response(
        url=f"{API_BASE}run",
        json="done",
        status_code=200,
    )
    async_venue.set_private(True)
    assert await async_venue.run("v/test/ops/echo", {}) == "done"

    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert body["private"] is True
    assert "wait" not in body


async def test_async_private_invoke_raises(httpx_mock, async_venue):
    async_venue.set_private(True)
    with pytest.raises(CoviaError, match="run\\(\\)"):
        await async_venue.invoke("v/test/ops/echo", {})
    assert len(httpx_mock.get_requests()) == 0


# ---------------------------------------------------------------------------
# ucan verify
# ---------------------------------------------------------------------------


def test_ucan_verify_shape(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}run",
        json={
            "valid": True,
            "iss": "did:key:zAlice",
            "aud": "did:key:zBob",
            "chainDepth": 0,
            "rootIssuer": "did:key:zAlice",
            "att": [{"with": "did:key:zAlice/w/shared/", "can": "crud/read", "rootAuthority": "owner"}],
            "authorises": True,
        },
        status_code=201,
    )
    result = venue.ucan.verify("eyJ...", with_="did:key:zAlice/w/shared/doc", can="crud/read", aud="did:key:zBob")
    assert result.valid is True
    assert result.chain_depth == 0
    assert result.root_issuer == "did:key:zAlice"
    assert result.att[0]["rootAuthority"] == "owner"
    assert result.authorises is True

    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert body["operation"] == "v/ops/ucan/verify"
    assert body["input"] == {
        "token": "eyJ...",
        "with": "did:key:zAlice/w/shared/doc",
        "can": "crud/read",
        "aud": "did:key:zBob",
    }


def test_ucan_verify_invalid_reason(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}run",
        json={"valid": False, "reason": "token expired"},
        status_code=201,
    )
    result = venue.ucan.verify("eyJ...")
    assert result.valid is False
    assert "expired" in result.reason
    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert body["input"] == {"token": "eyJ..."}
