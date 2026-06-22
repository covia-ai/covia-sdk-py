"""Tests for covia.did — DID and lattice-path helpers."""

from __future__ import annotations

import pytest

from covia.did import (
    DIDURL,
    Namespace,
    did_method,
    did_url,
    did_web_to_url,
    is_did,
    parse_did_url,
    url_to_did_web,
)


class TestIsDid:
    @pytest.mark.parametrize(
        "value",
        [
            "did:key:z6MkABC",
            "did:web:venue.covia.ai",
            "did:web:host%3A3000",
            "did:web:example.com:user:alice",
        ],
    )
    def test_valid(self, value):
        assert is_did(value)

    @pytest.mark.parametrize(
        "value",
        [
            "did:key:z6Mk.../w/foo",  # a DID URL, not a bare DID
            "did:key:",  # empty method-specific-id
            "did:",
            "not-a-did",
            "https://venue.covia.ai",
            "",
        ],
    )
    def test_invalid(self, value):
        assert not is_did(value)


class TestDidMethod:
    def test_key(self):
        assert did_method("did:key:z6Mk") == "key"

    def test_web(self):
        assert did_method("did:web:host") == "web"

    def test_non_did(self):
        assert did_method("w/foo") is None


class TestDidUrl:
    def test_with_did(self):
        assert did_url("did:key:zA", Namespace.WORKSPACE, "projects", "acme") == "did:key:zA/w/projects/acme"

    def test_relative(self):
        assert did_url(None, Namespace.WORKSPACE, "projects", "acme") == "w/projects/acme"

    def test_namespace_only(self):
        assert did_url("did:key:zA", Namespace.AGENT) == "did:key:zA/g"

    def test_strips_stray_slashes(self):
        assert did_url("did:key:zA", "w", "/a/", "b/") == "did:key:zA/w/a/b"

    def test_drops_empty_segments(self):
        assert did_url(None, "w", "", "x") == "w/x"

    def test_asset(self):
        assert did_url("did:web:v", Namespace.ASSET, "0xcafe") == "did:web:v/a/0xcafe"


class TestParseDidUrl:
    def test_full(self):
        assert parse_did_url("did:key:z6Mk/w/projects/acme") == DIDURL(
            did="did:key:z6Mk", namespace="w", path="projects/acme"
        )

    def test_relative(self):
        assert parse_did_url("w/foo") == DIDURL(did=None, namespace="w", path="foo")

    def test_relative_leading_slash(self):
        assert parse_did_url("/w/foo") == DIDURL(did=None, namespace="w", path="foo")

    def test_bare_did(self):
        assert parse_did_url("did:web:host") == DIDURL(did="did:web:host", namespace=None, path="")

    def test_did_web_path_separators_preserved(self):
        assert parse_did_url("did:web:example.com:u:alice/w/foo") == DIDURL(
            did="did:web:example.com:u:alice", namespace="w", path="foo"
        )

    def test_namespace_no_path(self):
        assert parse_did_url("did:key:zA/g") == DIDURL(did="did:key:zA", namespace="g", path="")

    @pytest.mark.parametrize(
        "did,ns,segs",
        [
            ("did:key:z6Mk", "w", ("projects", "acme")),
            (None, "o", ("my-op",)),
            ("did:web:host", "a", ("0xcafe",)),
        ],
    )
    def test_roundtrip(self, did, ns, segs):
        parsed = parse_did_url(did_url(did, ns, *segs))
        assert (parsed.did, parsed.namespace, parsed.path) == (did, ns, "/".join(segs))


class TestDidWeb:
    def test_bare_domain(self):
        assert did_web_to_url("did:web:venue.covia.ai") == "https://venue.covia.ai"

    def test_port(self):
        assert did_web_to_url("did:web:localhost%3A8080") == "https://localhost:8080"

    def test_path(self):
        assert did_web_to_url("did:web:example.com:user:alice") == "https://example.com/user/alice"

    def test_port_and_path(self):
        assert did_web_to_url("did:web:host%3A3000:a:b") == "https://host:3000/a/b"

    def test_not_did_web_raises(self):
        with pytest.raises(ValueError, match="did:web"):
            did_web_to_url("did:key:z6Mk")

    @pytest.mark.parametrize(
        "url",
        ["https://venue.covia.ai", "https://localhost:8080", "https://example.com/user/alice"],
    )
    def test_roundtrip(self, url):
        assert did_web_to_url(url_to_did_web(url)) == url
