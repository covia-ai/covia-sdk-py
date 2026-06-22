"""DID and lattice-path helpers for the Covia grid.

Covia addresses its lattice as ``<DID>/<namespace>/<path...>`` (see the venue's
``GRID_LATTICE_DESIGN``). This module centralises building and parsing those
addresses and converting between ``did:web`` DIDs and their HTTPS URLs, so the
rest of the SDK (and callers) don't hand-concatenate strings.

**Which DID belongs in a lattice address** — this is the part that's easy to
get wrong:

- ``w`` (workspace), ``o`` (operations), ``g`` (agents), ``j`` (jobs) and
  ``s`` (secrets) are **per-user**: the ``<DID>`` is the *owner's* DID — yours
  is your auth DID (e.g. :attr:`Ed25519Auth.did <covia.auth.Ed25519Auth.did>`),
  **not** the venue's. A UCAN ``with`` resource and any cross-user path must use
  the owner's DID; the venue rejects a UCAN ``with`` that doesn't start with the
  caller's own DID.
- ``a`` (assets) is venue-global and content-addressed; its ``<DID>`` is
  whichever venue serves the asset (this is the one case where the venue DID is
  the right prefix — see :attr:`Asset.did_url <covia.asset.Asset.did_url>`).
- A **namespace-relative** path (no ``<DID>``) resolves to the authenticated
  caller server-side, so you only need an explicit DID for cross-DID access.
"""

from __future__ import annotations

from dataclasses import dataclass


class Namespace:
    """Lattice namespace identifiers (see ``GRID_LATTICE_DESIGN`` §4)."""

    ASSET = "a"  # immutable, content-addressed; venue-global
    OPERATION = "o"  # mutable operation registry; per-user
    JOB = "j"  # job lifecycle records; per-user
    AGENT = "g"  # agents; per-user
    WORKSPACE = "w"  # freely mutable user data; per-user
    SECRET = "s"  # encrypted secrets; per-user, capability-gated
    # Virtual namespaces — resolved against the active request context:
    AGENT_SCRATCH = "n"  # agent-scoped scratch
    SESSION_SCRATCH = "c"  # session-scoped scratch
    JOB_SCRATCH = "t"  # job-scoped scratch
    VENUE = "v"  # venue globals


def is_did(value: str) -> bool:
    """True if *value* is a bare DID (``did:<method>:<method-specific-id>``).

    A DID *URL* (one carrying a ``/<namespace>/...`` path) returns ``False`` —
    use :func:`parse_did_url` for those.
    """
    if "/" in value:
        return False
    parts = value.split(":")
    return len(parts) >= 3 and parts[0] == "did" and all(parts[1:])


def did_method(value: str) -> str | None:
    """The DID method (e.g. ``"key"``, ``"web"``), or ``None`` if not a DID."""
    if not is_did(value):
        return None
    return value.split(":", 2)[1]


@dataclass(frozen=True)
class DIDURL:
    """A parsed lattice address.

    ``did`` is ``None`` for a namespace-relative path; ``namespace`` is ``None``
    for a bare DID with no path. ``path`` is the remainder after the namespace
    (possibly empty).
    """

    did: str | None
    namespace: str | None
    path: str


def parse_did_url(value: str) -> DIDURL:
    """Split a lattice address into its DID, namespace, and path.

    Handles bare DIDs (``did:key:z6Mk...``), namespace-relative paths
    (``w/foo`` or ``/w/foo``), and fully-qualified DID URLs
    (``did:key:z6Mk.../w/foo``). The ``did:web`` ``:`` path separators inside
    the DID itself are preserved as part of the DID.
    """
    did: str | None = None
    rest = value
    if value.startswith("did:"):
        slash = value.find("/")
        if slash == -1:
            return DIDURL(did=value, namespace=None, path="")
        did = value[:slash]
        rest = value[slash + 1 :]
    else:
        rest = value.lstrip("/")  # tolerate a leading slash on relative paths
    if not rest:
        return DIDURL(did=did, namespace=None, path="")
    head, _, tail = rest.partition("/")
    return DIDURL(did=did, namespace=head, path=tail)


def did_url(did: str | None, namespace: str, *segments: str) -> str:
    """Build a lattice address ``<did>/<namespace>/<segments...>``.

    Pass ``did=None`` for a namespace-relative path (resolves to the
    authenticated caller server-side). Segments are joined with ``/`` and any
    stray surrounding slashes are stripped; empty segments are dropped.

    Remember the ownership rules in the module docstring: for ``w``/``o``/``g``/
    ``j``/``s`` the *did* is the resource owner's DID, **not** the venue's.

    Example::

        did_url(auth.did, Namespace.WORKSPACE, "projects", "acme")
        # -> "did:key:z6Mk.../w/projects/acme"
    """
    tail = "/".join(seg.strip("/") for seg in segments if seg)
    base = f"{namespace}/{tail}" if tail else namespace
    return f"{did}/{base}" if did else base


def did_web_to_url(did: str, *, scheme: str = "https") -> str:
    """Resolve a ``did:web`` DID to its base URL, per the W3C did:web rules.

    The domain may encode a port as ``%3A``; additional ``:``-separated
    segments map to URL path segments
    (``did:web:host%3A3000:a:b`` → ``https://host:3000/a/b``).

    Raises:
        ValueError: If *did* is not a ``did:web`` DID.
    """
    if not did.startswith("did:web:"):
        raise ValueError(f"Not a did:web DID: {did!r}")
    segments = did[len("did:web:") :].split(":")
    host = segments[0].replace("%3A", ":")
    url = f"{scheme}://{host}"
    if len(segments) > 1:
        url += "/" + "/".join(segments[1:])
    return url


def url_to_did_web(url: str) -> str:
    """Convert an HTTP(S) URL to a ``did:web`` DID (inverse of :func:`did_web_to_url`)."""
    after = url.split("://", 1)[-1].rstrip("/")
    host, _, path = after.partition("/")
    did = f"did:web:{host.replace(':', '%3A')}"  # encode any port
    if path:
        did += ":" + path.replace("/", ":")
    return did
