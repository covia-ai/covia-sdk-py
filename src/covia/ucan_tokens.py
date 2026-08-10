"""Client-side UCAN minting for self-sovereign callers (covia-sdk-py#4).

These are the tokens a principal signs with their **own** key — a venue cannot
sign as the caller, so they have no venue-op counterpart; venues only verify.
Java parity: covia-core ``covia.grid.auth.UcanTokens``; TS parity:
``@covia/covia-sdk`` ``crypto/ucan``.

All helpers return the JWT encoding — the transport form carried in the
``ucans`` request array and relayed across cross-venue hops. Delegation chains
embed parent tokens as JWT strings in ``prf``.

Requires the ``signing`` extra: ``pip install covia[signing]``.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from covia.auth import _check_signing_deps, _public_key_to_did_key

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

#: The ability that instructs a venue to relay a cross-venue hop as itself.
VENUE_RELAY = "venue/relay"


def did_for(private_key: Ed25519PrivateKey) -> str:
    """The ``did:key`` DID for a private key."""
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    raw = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return _public_key_to_did_key(raw)


#: The Convex UCAN JWT profile version emitted in the ``ucv`` claim.
UCV_VERSION = "0.10.0"


def create_ucan_jwt(
    private_key: Ed25519PrivateKey,
    audience_did: str,
    att: list[dict[str, Any]],
    lifetime_seconds: int | None,
    proofs: list[str] | None = None,
) -> str:
    """Mint a UCAN as an EdDSA JWT in the Convex UCAN JWT profile:
    ``{iss, aud, ucv, att, prf, exp}`` signed by ``private_key`` (``iss`` = its
    did:key). From Convex 0.8.11 venues parse only this profile: the ``ucv``
    claim and the ``att``/``prf`` arrays are always present, and the ``exp``
    key is always present — explicitly ``null`` for a non-expiring token
    (UCAN v0.10.0; an absent ``exp`` is malformed).

    Args:
        private_key: The issuer's Ed25519 private key.
        audience_did: Who receives the token (``aud``).
        att: Capabilities delegated (``[{"with": ..., "can": ...}]``; empty
            list = pure identity token).
        lifetime_seconds: Validity window, or ``None`` for a non-expiring
            token (``exp: null``).
        proofs: Parent UCAN JWT strings (``prf``) for delegation chains.
    """
    _check_signing_deps()
    import jwt as pyjwt

    claims: dict[str, Any] = {
        "iss": did_for(private_key),
        "aud": audience_did,
        "ucv": UCV_VERSION,
        "att": att,
        "prf": list(proofs) if proofs else [],
        "exp": None if lifetime_seconds is None else int(time.time()) + lifetime_seconds,
    }
    token: str = pyjwt.encode(claims, private_key, algorithm="EdDSA")
    return token


def identity_token(private_key: Ed25519PrivateKey, venue_did: str, lifetime_seconds: int = 300) -> str:
    """Mint an **identity token**: a UCAN with an EMPTY attenuation list,
    audienced to ``venue_did``. Pure proof of identity — it grants nothing,
    and being audience-bound it is unusable at any other venue. Present it in
    the ``ucans`` array; the venue accepts it as the caller identity on an
    otherwise-unauthenticated transport (how identity crosses cross-venue
    relays — COG-3 §6, COG-15).
    """
    return create_ucan_jwt(private_key, venue_did, [], lifetime_seconds)


def grant(
    owner_private_key: Ed25519PrivateKey,
    audience_did: str,
    with_resource: str,
    can: str,
    lifetime_seconds: int,
) -> str:
    """Mint an owner-signed (**self-sovereign**) grant: delegates
    ``(with, can)`` to ``audience_did``, rooted by the signer. Because the
    root issuer is the resource owner, the grant verifies on **any** venue
    hosting the data — no venue involved in issuance.
    """
    return create_ucan_jwt(owner_private_key, audience_did, [{"with": with_resource, "can": can}], lifetime_seconds)


def relay_delegation(
    private_key: Ed25519PrivateKey,
    venue_did: str,
    lifetime_seconds: int,
    caps: list[dict[str, Any]] | None = None,
) -> str:
    """Mint a **relay delegation**: instructs and authorises ``venue_did`` to
    make a cross-venue hop authenticated as itself, exercising the caller's
    authority. Carries the ``venue/relay`` instruction plus the substantive
    capabilities the venue may exercise. The venue honours it only when its
    issuer is the authenticated caller (COG-15).
    """
    att: list[dict[str, Any]] = [{"with": did_for(private_key), "can": VENUE_RELAY}]
    if caps:
        att.extend(caps)
    return create_ucan_jwt(private_key, venue_did, att, lifetime_seconds)
