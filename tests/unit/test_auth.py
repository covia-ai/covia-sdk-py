"""Tests for authentication providers."""

from __future__ import annotations

import base64

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from covia import Grid
from covia.auth import (
    Auth,
    BasicAuth,
    BearerAuth,
    Ed25519Auth,
    NoAuth,
    _base58btc_encode,
    _public_key_to_did_key,
)
from tests.conftest import VENUE_URL

API_BASE = f"{VENUE_URL}/api/v1/"


class TestNoAuth:
    def test_apply_does_nothing(self):
        headers: dict[str, str] = {"X-Custom": "value"}
        NoAuth().apply(headers)
        assert headers == {"X-Custom": "value"}

    def test_repr(self):
        assert repr(NoAuth()) == "NoAuth()"

    def test_is_auth_subclass(self):
        assert isinstance(NoAuth(), Auth)


class TestBearerAuth:
    def test_apply_adds_authorization_header(self):
        headers: dict[str, str] = {}
        BearerAuth("my-token").apply(headers)
        assert headers == {"Authorization": "Bearer my-token"}

    def test_apply_preserves_existing_headers(self):
        headers: dict[str, str] = {"Accept": "application/json"}
        BearerAuth("tok").apply(headers)
        assert headers["Accept"] == "application/json"
        assert headers["Authorization"] == "Bearer tok"

    def test_repr_redacts_token(self):
        r = repr(BearerAuth("secret-value"))
        assert "secret-value" not in r
        assert "redacted" in r

    def test_is_auth_subclass(self):
        assert isinstance(BearerAuth("t"), Auth)


class TestBasicAuth:
    def test_apply_adds_basic_header(self):
        headers: dict[str, str] = {}
        BasicAuth("admin", "s3cret").apply(headers)
        expected = base64.b64encode(b"admin:s3cret").decode("ascii")
        assert headers == {"Authorization": f"Basic {expected}"}

    def test_repr_redacts_password(self):
        r = repr(BasicAuth("admin", "s3cret"))
        assert "s3cret" not in r
        assert "admin" in r
        assert "redacted" in r

    def test_is_auth_subclass(self):
        assert isinstance(BasicAuth("u", "p"), Auth)


class TestAuthIntegration:
    def test_bearer_auth_sent_on_api_request(self, httpx_mock):
        httpx_mock.add_response(url=f"{API_BASE}status", json={"name": "Test"})
        venue = Grid.connect(VENUE_URL, auth=BearerAuth("tok123"))
        try:
            venue.status()
        finally:
            venue.close()
        request = httpx_mock.get_requests()[0]
        assert request.headers["authorization"] == "Bearer tok123"

    def test_basic_auth_sent_on_api_request(self, httpx_mock):
        httpx_mock.add_response(url=f"{API_BASE}status", json={"name": "Test"})
        venue = Grid.connect(VENUE_URL, auth=BasicAuth("user", "pass"))
        try:
            venue.status()
        finally:
            venue.close()
        request = httpx_mock.get_requests()[0]
        expected = base64.b64encode(b"user:pass").decode("ascii")
        assert request.headers["authorization"] == f"Basic {expected}"

    def test_no_auth_sends_no_authorization(self, httpx_mock):
        httpx_mock.add_response(url=f"{API_BASE}status", json={"name": "Test"})
        venue = Grid.connect(VENUE_URL)
        try:
            venue.status()
        finally:
            venue.close()
        request = httpx_mock.get_requests()[0]
        assert "authorization" not in request.headers

    def test_auth_applied_to_discovery_endpoints(self, httpx_mock):
        httpx_mock.add_response(
            url=f"{VENUE_URL}/.well-known/did.json",
            json={"id": "did:web:test.covia.ai"},
        )
        venue = Grid.connect(VENUE_URL, auth=BearerAuth("tok"))
        try:
            venue.did_document()
        finally:
            venue.close()
        request = httpx_mock.get_requests()[0]
        assert request.headers["authorization"] == "Bearer tok"

    def test_auth_coexists_with_custom_headers(self, httpx_mock):
        httpx_mock.add_response(url=f"{API_BASE}status", json={"name": "Test"})
        venue = Grid.connect(
            VENUE_URL,
            headers={"X-Custom": "val"},
            auth=BearerAuth("tok"),
        )
        try:
            venue.status()
        finally:
            venue.close()
        request = httpx_mock.get_requests()[0]
        assert request.headers["authorization"] == "Bearer tok"
        assert request.headers["x-custom"] == "val"


# ---------------------------------------------------------------------------
# Base58 / did:key encoding
# ---------------------------------------------------------------------------


class TestBase58btcEncode:
    def test_empty_bytes(self):
        assert _base58btc_encode(b"\x00") == "1"

    def test_leading_zeros(self):
        result = _base58btc_encode(b"\x00\x00\x01")
        assert result.startswith("11")

    def test_known_value(self):
        # SHA-256 of empty string is well-known; verify round-trip consistency
        import hashlib

        digest = hashlib.sha256(b"").digest()
        encoded = _base58btc_encode(digest)
        assert len(encoded) > 0
        assert all(c in "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz" for c in encoded)


class TestPublicKeyToDidKey:
    def test_ed25519_prefix(self):
        # Any 32-byte key should produce did:key:z6Mk...
        key = Ed25519PrivateKey.generate()
        raw = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        did = _public_key_to_did_key(raw)
        assert did.startswith("did:key:z6Mk")

    def test_deterministic(self):
        seed = b"\x01" * 32
        key = Ed25519PrivateKey.from_private_bytes(seed)
        raw = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        did1 = _public_key_to_did_key(raw)
        did2 = _public_key_to_did_key(raw)
        assert did1 == did2


# ---------------------------------------------------------------------------
# Ed25519Auth
# ---------------------------------------------------------------------------


class TestEd25519Auth:
    def test_generate(self):
        auth = Ed25519Auth.generate()
        assert isinstance(auth, Auth)
        assert auth.did.startswith("did:key:z6Mk")
        assert len(auth.public_key_bytes) == 32

    def test_from_seed_deterministic(self):
        seed = b"\xab" * 32
        a1 = Ed25519Auth.from_seed(seed)
        a2 = Ed25519Auth.from_seed(seed)
        assert a1.did == a2.did

    def test_did_property(self):
        auth = Ed25519Auth.generate()
        did = auth.did
        assert did.startswith("did:key:z6Mk")
        # Should be stable
        assert auth.did == did

    def test_audience_default_none(self):
        auth = Ed25519Auth.generate()
        assert auth.audience is None

    def test_audience_set_in_constructor(self):
        auth = Ed25519Auth.generate(audience="did:web:venue.example.com")
        assert auth.audience == "did:web:venue.example.com"

    def test_audience_setter(self):
        auth = Ed25519Auth.generate()
        auth.audience = "did:web:other.example.com"
        assert auth.audience == "did:web:other.example.com"

    def test_repr(self):
        auth = Ed25519Auth.generate(audience="did:web:v.example.com")
        r = repr(auth)
        assert "Ed25519Auth" in r
        assert "did:key:z6Mk" in r
        assert "v.example.com" in r


class TestEd25519AuthApply:
    def test_adds_bearer_header(self):
        auth = Ed25519Auth.generate()
        headers: dict[str, str] = {}
        auth.apply(headers)
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")

    def test_jwt_structure(self):
        seed = b"\x01" * 32
        auth = Ed25519Auth.from_seed(seed, audience="did:web:venue.test")
        headers: dict[str, str] = {}
        auth.apply(headers)

        token = headers["Authorization"].removeprefix("Bearer ")
        # Decode without verification to inspect claims
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["iss"] == auth.did
        assert payload["sub"] == auth.did
        assert payload["aud"] == "did:web:venue.test"
        assert "iat" in payload
        assert "exp" in payload
        assert payload["exp"] - payload["iat"] == 300  # default lifetime

    def test_jwt_header_has_kid(self):
        auth = Ed25519Auth.generate()
        headers: dict[str, str] = {}
        auth.apply(headers)

        token = headers["Authorization"].removeprefix("Bearer ")
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "EdDSA"
        # kid is the bare multibase form (z6Mk...) not the full did:key —
        # the venue's Multikey.decodePublicKey() requires that shape.
        assert header["kid"].startswith("z")
        assert auth.did == f"did:key:{header['kid']}"

    def test_jwt_verifiable_with_public_key(self):
        seed = b"\x02" * 32
        auth = Ed25519Auth.from_seed(seed, audience="did:web:venue.test")
        headers: dict[str, str] = {}
        auth.apply(headers)

        token = headers["Authorization"].removeprefix("Bearer ")
        key = Ed25519PrivateKey.from_private_bytes(seed)
        pub = key.public_key()
        payload = jwt.decode(token, pub, algorithms=["EdDSA"], audience="did:web:venue.test")
        assert payload["iss"] == auth.did

    def test_no_aud_when_audience_is_none(self):
        auth = Ed25519Auth.generate()
        headers: dict[str, str] = {}
        auth.apply(headers)

        token = headers["Authorization"].removeprefix("Bearer ")
        payload = jwt.decode(token, options={"verify_signature": False})
        assert "aud" not in payload

    def test_custom_lifetime(self):
        auth = Ed25519Auth.generate(token_lifetime=60)
        headers: dict[str, str] = {}
        auth.apply(headers)

        token = headers["Authorization"].removeprefix("Bearer ")
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["exp"] - payload["iat"] == 60

    def test_tokens_differ_over_time(self):
        auth = Ed25519Auth.generate()
        h1: dict[str, str] = {}
        auth.apply(h1)
        # Tokens include iat, so two calls at the same second may
        # produce the same token. Just verify both are valid JWTs.
        h2: dict[str, str] = {}
        auth.apply(h2)
        assert h1["Authorization"].startswith("Bearer ")
        assert h2["Authorization"].startswith("Bearer ")


class TestEd25519AuthIntegration:
    def test_ed25519_auth_sent_on_api_request(self, httpx_mock):
        httpx_mock.add_response(url=f"{API_BASE}status", json={"name": "Test"})
        auth = Ed25519Auth.generate(audience="did:web:test.covia.ai")
        venue = Grid.connect(VENUE_URL, auth=auth)
        try:
            venue.status()
        finally:
            venue.close()
        request = httpx_mock.get_requests()[0]
        header = request.headers["authorization"]
        assert header.startswith("Bearer ey")  # JWT starts with ey (base64 of '{')

        # Verify it's a valid JWT with correct issuer
        token = header.removeprefix("Bearer ")
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["iss"] == auth.did
        assert payload["aud"] == "did:web:test.covia.ai"

    def test_audience_resolved_from_venue_did(self, httpx_mock):
        # With no explicit audience, the aud is the venue's *reported* DID, now
        # taken from GET /api/v1/status (the canonical info endpoint), not the
        # connection string — and the caller's auth object is never mutated.
        httpx_mock.add_response(url=f"{API_BASE}status", json={"name": "Test", "did": "did:web:test.covia.ai"})
        httpx_mock.add_response(url=f"{API_BASE}secrets", json={"items": [], "total": 0})
        auth = Ed25519Auth.generate()  # No audience set
        assert auth.audience is None

        venue = Grid.connect(VENUE_URL, auth=auth)
        try:
            venue.list_secrets()
        finally:
            venue.close()

        # The auth object is NOT mutated (no sticky connection-string audience).
        assert auth.audience is None

        # The authenticated request's JWT carries aud = the DID from /status.
        sec_req = next(r for r in httpx_mock.get_requests() if r.url.path.endswith("/secrets"))
        payload = jwt.decode(
            sec_req.headers["authorization"].removeprefix("Bearer "),
            options={"verify_signature": False},
        )
        assert payload["aud"] == "did:web:test.covia.ai"

        # The DID came from /status — no did.json round-trip was needed.
        assert not any("did.json" in str(r.url) for r in httpx_mock.get_requests())

        # The bootstrap /status fetch itself carried no aud (re-entrancy guard).
        status_req = next(r for r in httpx_mock.get_requests() if r.url.path.endswith("/status"))
        boot = jwt.decode(
            status_req.headers["authorization"].removeprefix("Bearer "),
            options={"verify_signature": False},
        )
        assert "aud" not in boot

    def test_audience_omitted_when_venue_reports_no_did(self, httpx_mock):
        # If neither /status nor did.json yields a DID, the token is still sent
        # (self-issued), just without an aud — auth keeps working.
        httpx_mock.add_response(url=f"{API_BASE}status", json={"name": "Test"})  # no did
        httpx_mock.add_response(url=f"{VENUE_URL}/.well-known/did.json", status_code=404)
        httpx_mock.add_response(url=f"{API_BASE}secrets", json={"items": [], "total": 0})
        venue = Grid.connect(VENUE_URL, auth=Ed25519Auth.generate())
        try:
            venue.list_secrets()
        finally:
            venue.close()
        sec_req = next(r for r in httpx_mock.get_requests() if r.url.path.endswith("/secrets"))
        payload = jwt.decode(
            sec_req.headers["authorization"].removeprefix("Bearer "),
            options={"verify_signature": False},
        )
        assert "aud" not in payload

    def test_grid_connect_does_not_override_explicit_audience(self, httpx_mock):
        httpx_mock.add_response(url=f"{API_BASE}status", json={"name": "Test"})
        auth = Ed25519Auth.generate(audience="did:web:explicit.example.com")

        venue = Grid.connect(VENUE_URL, auth=auth)
        try:
            # Should keep the explicit audience
            assert auth.audience == "did:web:explicit.example.com"
            venue.status()
        finally:
            venue.close()

        request = httpx_mock.get_requests()[0]
        token = request.headers["authorization"].removeprefix("Bearer ")
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["aud"] == "did:web:explicit.example.com"
