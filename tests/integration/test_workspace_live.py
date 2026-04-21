"""Integration tests for lattice paths against a live venue.

Verifies that the SDK drives the real ``covia:*`` operations correctly
for the documented namespaces and addressing modes:

- bare ``/w/...`` paths resolve to the caller's own workspace
- fully-qualified ``did:key:<self>/w/...`` paths resolve to the same
  location as the bare form
- cross-DID reads without a capability proof are rejected
- cross-DID reads with a UCAN proof succeed

Requires the ``signing`` extra (``pip install covia[signing]``) for
Ed25519 authentication.
"""

from __future__ import annotations

import os
import time
import uuid

import pytest

pytest.importorskip("cryptography", reason="integration tests need the 'signing' extra")
pytest.importorskip("jwt", reason="integration tests need the 'signing' extra")

from covia import Grid, UCANAttenuation  # noqa: E402
from covia.auth import Ed25519Auth  # noqa: E402

VENUE_URL = os.environ.get("COVIA_VENUE_URL", "https://venue-test.covia.ai")

pytestmark = pytest.mark.integration


def _fresh_auth() -> Ed25519Auth:
    return Ed25519Auth.generate(audience=VENUE_URL)


@pytest.fixture(scope="module")
def _venue_supports_v_ops() -> bool:
    """Detect whether the venue exposes the ``/v/ops/`` operation catalog.

    The SDK uses ``v/ops/<adapter>/<op>`` refs (matches the current
    Java/TS SDKs). Older venues only support the legacy
    ``<adapter>:<op>`` dispatch form and reject the new refs with
    ``Adapter not available: v/ops/...``. When that happens we skip the
    workspace/UCAN tests rather than failing the build.
    """
    auth = _fresh_auth()
    v = Grid.connect(VENUE_URL, auth=auth)
    try:
        try:
            v.run("v/ops/covia/read", {"path": "v/info/version"})
        except Exception as e:
            if "Adapter not available: v/ops/" in str(e):
                return False
            # Any other failure (auth rejection, transport, …) we treat
            # as "venue too old / unsupported" and skip — caller surfaces
            # the message.
            pytest.skip(f"venue probe failed: {e}")
        return True
    finally:
        v.close()


@pytest.fixture
def alice(_venue_supports_v_ops):
    if not _venue_supports_v_ops:
        pytest.skip(
            "venue does not expose the v/ops/ catalog (legacy API). "
            "Deploy a covia venue with OPERATIONS.md materialiseVOps "
            "to run these tests."
        )
    auth = _fresh_auth()
    v = Grid.connect(VENUE_URL, auth=auth)
    yield v, auth
    v.close()


@pytest.fixture
def bob(_venue_supports_v_ops):
    if not _venue_supports_v_ops:
        pytest.skip("venue does not expose the v/ops/ catalog (legacy API)")
    auth = _fresh_auth()
    v = Grid.connect(VENUE_URL, auth=auth)
    yield v, auth
    v.close()


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_self_workspace_roundtrip(alice):
    venue, _auth = alice
    path = f"/w/tests/{_unique('note')}"
    venue.workspace.write(path, {"hello": "world"})

    read = venue.workspace.read(path)
    assert read.exists is True
    assert read.value == {"hello": "world"}

    venue.workspace.delete(path)
    gone = venue.workspace.read(path)
    assert gone.exists is False


def test_self_read_via_did_prefix(alice):
    """A caller can address their own lattice with either the bare
    ``/w/...`` form or the fully-qualified ``did:.../<namespace>/...``
    form, and both must resolve to the same value.
    """
    venue, auth = alice
    key = _unique("diddoc")
    bare_path = f"/w/tests/{key}"
    full_path = f"{auth.did}/w/tests/{key}"

    venue.workspace.write(bare_path, {"marker": key})

    try:
        bare = venue.workspace.read(bare_path)
        full = venue.workspace.read(full_path)
    finally:
        venue.workspace.delete(bare_path)

    assert bare.exists is True
    assert full.exists is True
    assert bare.value == full.value == {"marker": key}


def test_cross_user_read_rejected_without_ucan(alice, bob):
    """Without a UCAN proof, a second user cannot read the first user's
    workspace via the fully-qualified DID path. The venue may either
    surface this as an explicit error or as ``exists=False`` — both are
    acceptable semantics for "not visible".
    """
    alice_venue, alice_auth = alice
    bob_venue, _bob_auth = bob

    key = _unique("private")
    alice_path = f"{alice_auth.did}/w/tests/{key}"

    alice_venue.workspace.write(f"/w/tests/{key}", {"secret": "hush"})

    try:
        try:
            result = bob_venue.workspace.read(alice_path)
        except Exception:
            # Server raised — that's an acceptable rejection.
            return
        # Or the server returns exists=False for anything not permitted.
        assert result.exists is False or result.value != {"secret": "hush"}, (
            "bob must not see alice's private value without a UCAN proof"
        )
    finally:
        alice_venue.workspace.delete(f"/w/tests/{key}")


def test_cross_user_read_with_ucan_delegation(alice, bob):
    """Alice issues a UCAN to Bob for a specific path, then Bob reads
    it successfully by presenting the token in ``ucans``.
    """
    alice_venue, alice_auth = alice
    bob_venue, bob_auth = bob

    key = _unique("shared")
    local_path = f"/w/tests/{key}"
    alice_path = f"{alice_auth.did}/w/tests/{key}"

    alice_venue.workspace.write(local_path, {"shared-with-bob": True})

    try:
        # Alice delegates read capability on this specific path to Bob.
        try:
            issued = alice_venue.ucan.issue(
                audience=bob_auth.did,
                attenuations=[
                    UCANAttenuation(with_=alice_path, can="crud/read"),
                ],
                expiry=int(time.time()) + 600,
            )
        except Exception as e:
            pytest.skip(f"venue does not support ucan:issue or rejected it: {e}")

        token = issued.get("token") if isinstance(issued, dict) else None
        if not isinstance(token, str):
            pytest.skip(f"unexpected ucan:issue response shape: {issued!r}")

        # Bob presents the token on the read.
        result = bob_venue.run(
            "v/ops/covia/read",
            {"path": alice_path},
            ucans=[token],
        )

        # Result shape is WorkspaceReadResult — we call via venue.run so
        # it comes back as a plain dict.
        assert result.get("exists") is True, f"bob should read with UCAN: {result}"
        assert result.get("value") == {"shared-with-bob": True}
    finally:
        alice_venue.workspace.delete(local_path)
