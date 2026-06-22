"""Authentication providers for the Covia SDK.

Provides a generic :class:`Auth` interface and built-in implementations
for common authentication strategies.

Built-in providers:

- :class:`NoAuth` — no authentication (default when ``auth`` is omitted)
- :class:`BearerAuth` — ``Authorization: Bearer <token>``
- :class:`BasicAuth` — HTTP Basic authentication (``username:password``)
- :class:`Ed25519Auth` — self-issued EdDSA JWT signed with Ed25519
  (requires ``covia[signing]``)

The interface is designed to accommodate future providers without
breaking changes:

- **OAuth 2.0** — token acquisition, refresh, and injection
"""

from __future__ import annotations

import base64
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class Auth(ABC):
    """Base class for Covia authentication providers.

    Subclass this to implement custom authentication strategies.
    :meth:`apply` is called before every HTTP request to inject
    credentials into the outgoing request headers.

    Example — custom API-key auth::

        class ApiKeyAuth(Auth):
            def __init__(self, key: str) -> None:
                self._key = key

            def apply(self, headers: dict[str, str], audience: str | None = None) -> None:
                headers["X-Api-Key"] = self._key
    """

    @property
    def wants_audience(self) -> bool:
        """Whether the transport should resolve the venue's DID and pass it as
        the *audience* to :meth:`apply`.

        Default ``False``. Providers that bind tokens to the venue's identity
        (e.g. :class:`Ed25519Auth` with no explicit audience) override this to
        ``True``; the transport then resolves the venue's reported DID (from
        ``/.well-known/did.json``) once and supplies it on every call.
        """
        return False

    @abstractmethod
    def apply(self, headers: dict[str, str], audience: str | None = None) -> None:
        """Apply authentication credentials to request headers.

        Implementations should mutate *headers* in place, adding any
        fields required by the venue's authentication scheme.

        Args:
            headers: Mutable dict of HTTP headers for the outgoing request.
            audience: The venue's resolved DID, supplied by the transport when
                :attr:`wants_audience` is ``True``. Providers that don't need
                it (the default) ignore this argument.
        """


class NoAuth(Auth):
    """No-op authentication provider.

    Explicitly signals that no credentials should be sent.
    Equivalent to omitting the ``auth`` parameter entirely.
    """

    def apply(self, headers: dict[str, str], audience: str | None = None) -> None:
        pass

    def __repr__(self) -> str:
        return "NoAuth()"


class BearerAuth(Auth):
    """Bearer token authentication.

    Adds ``Authorization: Bearer <token>`` to every request.

    Example::

        from covia import Grid
        from covia.auth import BearerAuth

        venue = Grid.connect(
            "https://venue.covia.ai",
            auth=BearerAuth("my-secret-token"),
        )
    """

    def __init__(self, token: str) -> None:
        self._token = token

    def apply(self, headers: dict[str, str], audience: str | None = None) -> None:
        headers["Authorization"] = f"Bearer {self._token}"

    def __repr__(self) -> str:
        return "BearerAuth(token=<redacted>)"


class BasicAuth(Auth):
    """HTTP Basic authentication.

    Adds ``Authorization: Basic <base64(username:password)>`` to every request.

    Example::

        from covia.auth import BasicAuth

        venue = Grid.connect(
            "https://venue.covia.ai",
            auth=BasicAuth("admin", "s3cret"),
        )
    """

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    def apply(self, headers: dict[str, str], audience: str | None = None) -> None:
        credentials = base64.b64encode(f"{self._username}:{self._password}".encode()).decode("ascii")
        headers["Authorization"] = f"Basic {credentials}"

    def __repr__(self) -> str:
        return f"BasicAuth(username={self._username!r}, password=<redacted>)"


# ---------------------------------------------------------------------------
# Ed25519 self-issued JWT auth
# ---------------------------------------------------------------------------

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_ED25519_MULTICODEC = b"\xed\x01"


def _base58btc_encode(data: bytes) -> str:
    """Encode bytes as base58btc (Bitcoin alphabet)."""
    n_pad = len(data) - len(data.lstrip(b"\x00"))
    n = int.from_bytes(data, "big")
    if n == 0:
        return "1" * max(n_pad, 1)
    chars: list[str] = []
    while n > 0:
        n, r = divmod(n, 58)
        chars.append(_B58_ALPHABET[r])
    return "1" * n_pad + "".join(reversed(chars))


def _public_key_to_multibase(public_key_bytes: bytes) -> str:
    """Encode a 32-byte Ed25519 public key as a base58btc multibase
    string (``z<base58btc(0xED01 || pubkey)>``).
    """
    return f"z{_base58btc_encode(_ED25519_MULTICODEC + public_key_bytes)}"


def _public_key_to_did_key(public_key_bytes: bytes) -> str:
    """Encode a 32-byte Ed25519 public key as a ``did:key`` DID."""
    return f"did:key:{_public_key_to_multibase(public_key_bytes)}"


def _check_signing_deps() -> None:
    """Raise a clear error if signing dependencies are not installed."""
    try:
        import cryptography  # noqa: F401
        import jwt  # noqa: F401
    except ImportError as e:
        raise ImportError("Ed25519Auth requires the 'signing' extra: pip install covia[signing]") from e


class Ed25519Auth(Auth):
    """Self-issued EdDSA JWT authentication using an Ed25519 key pair.

    Each request carries a short-lived JWT in the ``Authorization: Bearer``
    header. The JWT is signed with the client's Ed25519 private key and
    includes the client's ``did:key`` as the ``iss`` (issuer) claim. The
    venue verifies the signature by extracting the public key from the DID.

    Requires the ``signing`` extra::

        pip install covia[signing]

    Example::

        from covia import Grid
        from covia.auth import Ed25519Auth

        auth = Ed25519Auth.generate(audience="did:web:venue.covia.ai")
        print(auth.did)  # did:key:z6Mk...

        with Grid.connect("did:web:venue.covia.ai", auth=auth) as venue:
            result = venue.run("my-operation", {"prompt": "hello"})
    """

    def __init__(
        self,
        private_key: Ed25519PrivateKey,
        *,
        audience: str | None = None,
        token_lifetime: int = 300,
    ) -> None:
        _check_signing_deps()
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        self._private_key = private_key
        raw = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self._public_key_bytes = raw
        self._multibase = _public_key_to_multibase(raw)
        self._did = f"did:key:{self._multibase}"
        self._audience = audience
        self._token_lifetime = token_lifetime

    @classmethod
    def generate(
        cls,
        *,
        audience: str | None = None,
        token_lifetime: int = 300,
    ) -> Ed25519Auth:
        """Generate a new random Ed25519 key pair.

        Args:
            audience: Venue DID or URL for the JWT ``aud`` claim.
            token_lifetime: JWT validity in seconds (default 300).
        """
        _check_signing_deps()
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        return cls(
            Ed25519PrivateKey.generate(),
            audience=audience,
            token_lifetime=token_lifetime,
        )

    @classmethod
    def from_seed(
        cls,
        seed: bytes,
        *,
        audience: str | None = None,
        token_lifetime: int = 300,
    ) -> Ed25519Auth:
        """Create from a 32-byte Ed25519 seed (private key bytes).

        Args:
            seed: 32-byte Ed25519 private key seed.
            audience: Venue DID or URL for the JWT ``aud`` claim.
            token_lifetime: JWT validity in seconds (default 300).
        """
        _check_signing_deps()
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        return cls(
            Ed25519PrivateKey.from_private_bytes(seed),
            audience=audience,
            token_lifetime=token_lifetime,
        )

    @property
    def did(self) -> str:
        """The ``did:key`` DID derived from the Ed25519 public key."""
        return self._did

    @property
    def public_key_bytes(self) -> bytes:
        """The raw 32-byte Ed25519 public key."""
        return self._public_key_bytes

    @property
    def audience(self) -> str | None:
        """Explicitly-pinned JWT ``aud`` value, or ``None`` to use the venue's
        reported DID.

        When ``None`` (the default), the transport resolves the venue's DID
        from ``/.well-known/did.json`` and supplies it as the audience — so
        the token is bound to the venue's actual identity rather than however
        you happened to address it. Set this only to override that.
        """
        return self._audience

    @audience.setter
    def audience(self, value: str | None) -> None:
        self._audience = value

    @property
    def wants_audience(self) -> bool:
        # Ask the transport for the venue DID only when no audience is pinned.
        return self._audience is None

    def apply(self, headers: dict[str, str], audience: str | None = None) -> None:
        import jwt

        now = int(time.time())
        payload: dict[str, object] = {
            "iss": self._did,
            "sub": self._did,
            "iat": now,
            "exp": now + self._token_lifetime,
        }
        # An explicitly-pinned audience wins; otherwise use the venue DID the
        # transport resolved and supplied. Omit `aud` entirely if neither is
        # available — the venue treats a no-aud token as a plain self-issued
        # identity assertion.
        aud = self._audience if self._audience is not None else audience
        if aud is not None:
            payload["aud"] = aud
        # The venue's auth middleware uses Multikey.decodePublicKey on the
        # `kid` header — that decoder requires the bare multibase string
        # (z6Mk...) and rejects the full did:key form.
        token: str = jwt.encode(
            payload,
            self._private_key,
            algorithm="EdDSA",
            headers={"kid": self._multibase},
        )
        headers["Authorization"] = f"Bearer {token}"

    def __repr__(self) -> str:
        return f"Ed25519Auth(did={self._did!r}, audience={self._audience!r})"
