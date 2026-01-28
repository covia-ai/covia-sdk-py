"""Tests for authentication providers."""

from __future__ import annotations

import base64

from covia import Grid
from covia.auth import Auth, BasicAuth, BearerAuth, NoAuth
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
