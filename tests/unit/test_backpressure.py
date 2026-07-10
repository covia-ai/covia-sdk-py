"""Deterministic tests for 429 backpressure handling, job-free agent reads,
and client-side UCAN minting (covia-sdk-py#3, #4).

Retry decisions are pure (random supplied explicitly); the loop tests use
``Retry-After: 0`` so nothing depends on timing.
"""

from __future__ import annotations

import json

import pytest

from covia import RateLimitError
from covia._retry import parse_retry_after_ms, retry_delay_ms
from tests.conftest import VENUE_URL

API_BASE = f"{VENUE_URL}/api/v1/"


# ── retry policy (pure) ─────────────────────────────────────────────────────

def test_retry_after_is_floor():
    assert retry_delay_ms(1, 3000, 60_000, 0.0) == 3000


def test_full_jitter_within_backoff():
    # attempt 3 → backoff = 200 * 2^2 = 800; random 0.5 → 400
    assert retry_delay_ms(3, 0, 60_000, 0.5) == 400
    assert retry_delay_ms(3, 0, 60_000, 0.999) < 800


def test_gives_up_at_max_attempts_and_over_budget():
    assert retry_delay_ms(4, 0, 60_000, 0.0) == -1
    assert retry_delay_ms(1, 5000, 1000, 0.0) == -1


def test_parse_retry_after_forms():
    assert parse_retry_after_ms("5", 0) == 5000
    assert parse_retry_after_ms(None, 0) == 0
    assert parse_retry_after_ms("garbage", 0) == 0


# ── 429 loop over the mocked transport (Retry-After: 0 → no timing) ─────────

def test_429_retried_then_succeeds(httpx_mock, venue):
    httpx_mock.add_response(url=f"{API_BASE}status", status_code=429,
        headers={"Retry-After": "0"}, json={"error": "Rate limit exceeded"})
    httpx_mock.add_response(url=f"{API_BASE}status", json={"name": "v", "did": "did:key:z1"})
    status = venue.status()
    assert status.name == "v"
    assert len(httpx_mock.get_requests()) >= 2


def test_429_exhaustion_raises_rate_limit_error(httpx_mock, venue):
    for _ in range(4):  # 1 try + 3 retries
        httpx_mock.add_response(url=f"{API_BASE}status", status_code=429,
            headers={"Retry-After": "0"}, json={"error": "Rate limit exceeded"})
    with pytest.raises(RateLimitError) as exc:
        venue.status()
    assert exc.value.retry_after_seconds >= 1
    assert len(httpx_mock.get_requests()) == 4


# ── job-free agent reads (#180) ─────────────────────────────────────────────

def test_agents_list_uses_get(httpx_mock, venue):
    httpx_mock.add_response(url=f"{API_BASE}agents?includeTerminated=true",
        json={"agents": [{"agentId": "a1", "status": "SLEEPING", "tasks": 0}]})
    result = venue.agents.list(include_terminated=True)
    assert result.agents[0].agentId == "a1"
    sent = httpx_mock.get_requests()[-1]
    assert sent.method == "GET"           # no job path
    assert "/api/v1/agents" in str(sent.url)


def test_agents_info_uses_get_and_falls_back_on_404(httpx_mock, venue):
    httpx_mock.add_response(url=f"{API_BASE}agents/a1",
        json={"agentId": "a1", "status": "SLEEPING", "tasks": 0})
    info = venue.agents.info("a1")
    assert info.agentId == "a1"

    # Old venue: GET 404s once → falls back to the invoke path, remembered.
    httpx_mock.add_response(url=f"{API_BASE}agents/a2", status_code=404,
        json={"error": "not found"})
    httpx_mock.add_response(url=f"{API_BASE}invoke", status_code=201, json={
        "id": "j1", "status": "COMPLETE", "output": {"agentId": "a2", "status": "SLEEPING"}})
    info2 = venue.agents.info("a2")
    assert info2.agentId == "a2"
    # Subsequent reads skip the GET probe entirely (invoke path directly).
    httpx_mock.add_response(url=f"{API_BASE}invoke", status_code=201, json={
        "id": "j2", "status": "COMPLETE", "output": {"agents": []}})
    venue.agents.list()
    assert not any("/agents?" in str(r.url) or str(r.url).endswith("/agents")
                   for r in httpx_mock.get_requests()[-1:])


# ── UCAN minting shapes ─────────────────────────────────────────────────────

def _decode(jwt_str: str) -> dict:
    import base64
    payload = jwt_str.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def test_ucan_minting_shapes():
    pytest.importorskip("cryptography")
    pytest.importorskip("jwt")
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from covia import VENUE_RELAY, create_ucan_jwt, did_for, grant, identity_token, relay_delegation

    kp = Ed25519PrivateKey.generate()
    venue_did = "did:key:z6MkVenueExample"

    ident = _decode(identity_token(kp, venue_did, 300))
    assert ident["iss"] == did_for(kp)
    assert ident["aud"] == venue_did
    assert ident["att"] == []             # pure identity — grants nothing

    g = _decode(grant(kp, "did:key:z6MkBob", "did:key:zAlice/w/shared/", "crud/read", 3600))
    assert g["att"] == [{"with": "did:key:zAlice/w/shared/", "can": "crud/read"}]
    assert "prf" not in g                 # root grant

    r = _decode(relay_delegation(kp, venue_did, 300, [{"with": "w/", "can": "crud/read"}]))
    assert r["att"][0] == {"with": did_for(kp), "can": VENUE_RELAY}
    assert r["att"][1] == {"with": "w/", "can": "crud/read"}

    root = grant(kp, "did:key:z6MkBob", "w/", "crud", 3600)
    kp2 = Ed25519PrivateKey.generate()
    leaf = _decode(create_ucan_jwt(kp2, "did:key:z6MkCarol",
        [{"with": "w/shared/", "can": "crud/read"}], 3600, [root]))
    assert leaf["prf"] == [root]          # chains embed parent JWTs
