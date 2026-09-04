"""Tests for UCANManager."""

from __future__ import annotations

import json

from covia import UCANAttenuation
from tests.conftest import VENUE_URL

API_BASE = f"{VENUE_URL}/api/v1/"


def _complete(output: object) -> object:
    return output


def test_issue_with_attenuation_models(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}run",
        json=_complete({"token": "eyJ..."}),
        status_code=201,
    )
    atts = [UCANAttenuation(with_="did:key:zAlice/w/shared", can="crud/read")]
    result = venue.ucan.issue("did:key:zBob", atts, expiry=2_000_000_000)
    assert result.token == "eyJ..."

    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert body["operation"] == "v/ops/ucan/issue"
    # attenuations serialise back to "with" (the wire alias) not "with_"
    assert body["input"]["att"] == [{"with": "did:key:zAlice/w/shared", "can": "crud/read"}]
    assert body["input"]["aud"] == "did:key:zBob"
    assert body["input"]["exp"] == 2_000_000_000


def test_issue_with_raw_dicts(httpx_mock, venue):
    httpx_mock.add_response(
        url=f"{API_BASE}run",
        json=_complete({"token": "eyJ..."}),
        status_code=201,
    )
    atts: list[dict[str, object]] = [{"with": "did:key:zAlice/w/shared", "can": "crud/read"}]
    venue.ucan.issue("did:key:zBob", atts, expiry=2_000_000_000)
    body = json.loads(httpx_mock.get_requests()[-1].content)
    assert body["input"]["att"] == [{"with": "did:key:zAlice/w/shared", "can": "crud/read"}]


def test_lazy_manager_is_cached(venue):
    assert venue.ucan is venue.ucan
