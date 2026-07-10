"""Tests for connection-level private-jobs mode (covia #192) and ucan verify.

Deterministic — a mocked transport returns a terminal record from the single
invoke request, mirroring the venue's ``wait`` window. Private mode must send
``private``/``wait`` in the invoke body, collect the result from that one
response (a completed private job is immediately forgotten — polling 404s),
and refuse poll-style ``invoke``.
"""

from __future__ import annotations

import json

import pytest

from covia.exceptions import CoviaError, CoviaTimeoutError, JobFailedError
from tests.conftest import VENUE_URL

API_BASE = f"{VENUE_URL}/api/v1/"


def _record(status: str, output: object = None, error: str | None = None) -> dict[str, object]:
    rec: dict[str, object] = {"id": "job-private", "status": status}
    if output is not None:
        rec["output"] = output
    if error is not None:
        rec["error"] = error
    return rec


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


def test_private_run_single_request_no_polling(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_record("COMPLETE", output={"echo": "hi"}),
        status_code=200,
    )
    venue.set_private(True)
    result = venue.run("v/test/ops/echo", {"echo": "hi"})
    assert result == {"echo": "hi"}

    requests = httpx_mock.get_requests()
    assert len(requests) == 1, "private run must not poll — one invoke only"
    body = json.loads(requests[0].content)
    assert body["private"] is True
    assert body["wait"] is True


def test_private_run_timeout_sends_wait_ms(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_record("COMPLETE", output=42),
        status_code=200,
    )
    venue.set_private(True)
    assert venue.run("v/test/ops/echo", {}, timeout=5.0) == 42
    body = json.loads(httpx_mock.get_requests()[0].content)
    assert body["wait"] == 5000


def test_private_run_failed_raises_job_failed(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_record("FAILED", error="boom"),
        status_code=200,
    )
    venue.set_private(True)
    with pytest.raises(JobFailedError):
        venue.run("v/test/ops/fail", {})


def test_private_run_unfinished_raises_timeout(httpx_mock, venue):
    # Venue's wait window elapsed before completion — record still STARTED.
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_record("STARTED"),
        status_code=200,
    )
    venue.set_private(True)
    with pytest.raises(CoviaTimeoutError, match="private"):
        venue.run("v/test/ops/never", {}, timeout=0.1)


def test_private_invoke_raises_without_request(httpx_mock, venue):
    venue.set_private(True)
    with pytest.raises(CoviaError, match="run\\(\\)"):
        venue.invoke("v/test/ops/echo", {})
    assert len(httpx_mock.get_requests()) == 0, "must fail before any HTTP request"


def test_set_private_false_restores_normal_invoke(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}invoke",
        json=_record("PENDING"),
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
        url=f"{API_BASE}invoke",
        json=_record("COMPLETE", output="done"),
        status_code=200,
    )
    async_venue.set_private(True)
    assert await async_venue.run("v/test/ops/echo", {}) == "done"

    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert body["private"] is True
    assert body["wait"] is True


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
        url=f"{API_BASE}invoke",
        json={
            "id": "job-verify",
            "status": "COMPLETE",
            "output": {
                "valid": True,
                "iss": "did:key:zAlice",
                "aud": "did:key:zBob",
                "chainDepth": 0,
                "rootIssuer": "did:key:zAlice",
                "att": [{"with": "did:key:zAlice/w/shared/", "can": "crud/read", "rootAuthority": "owner"}],
                "authorises": True,
            },
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
        url=f"{API_BASE}invoke",
        json={
            "id": "job-verify",
            "status": "COMPLETE",
            "output": {"valid": False, "reason": "token expired"},
        },
        status_code=201,
    )
    result = venue.ucan.verify("eyJ...")
    assert result.valid is False
    assert "expired" in result.reason
    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert body["input"] == {"token": "eyJ..."}
