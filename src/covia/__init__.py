"""Covia Python SDK — federated AI orchestration grid client.

Connect to a Covia venue and invoke operations::

    from covia import Grid

    with Grid.connect("https://venue.covia.ai") as venue:
        result = venue.run("my-operation", {"prompt": "hello"})
"""

from covia.agents import AgentManager
from covia.asset import Asset
from covia.auth import Auth, BasicAuth, BearerAuth, Ed25519Auth, NoAuth
from covia.did import (
    DIDURL,
    Namespace,
    asset_hash,
    did_method,
    did_url,
    did_web_to_url,
    is_did,
    parse_did_url,
    url_to_did_web,
)
from covia.exceptions import (
    AssetNotFoundError,
    CoviaConnectionError,
    CoviaError,
    CoviaTimeoutError,
    GridError,
    JobFailedError,
    JobNotFoundError,
    NotFoundError,
)
from covia.grid import Grid
from covia.job import Job
from covia.models import (
    AgentCard,
    AgentChatResult,
    AgentCreateResult,
    AgentDeleteResult,
    AgentListEntry,
    AgentListResult,
    AgentMessageResult,
    AgentQueryResult,
    AgentRequestResult,
    AgentSuspendResult,
    AgentTriggerResult,
    AssetList,
    DIDDocument,
    GroupCount,
    InvokeRequest,
    JobData,
    MCPDiscovery,
    OperationInfo,
    SecretExtractResult,
    SecretSetResult,
    UCANAttenuation,
    UCANIssueResult,
    VenueStatus,
    WorkspaceAggregateResult,
    WorkspaceAppendResult,
    WorkspaceCountResult,
    WorkspaceDeleteResult,
    WorkspaceInspectResult,
    WorkspaceListResult,
    WorkspaceReadResult,
    WorkspaceSliceResult,
    WorkspaceWriteResult,
)
from covia.secrets import SecretManager
from covia.status import JobStatus
from covia.ucan import UCANManager
from covia.venue import Venue
from covia.workspace import WorkspaceManager

# Single source of truth for the package version. Hatchling reads this literal
# at build time (see [tool.hatch.version] in pyproject.toml), so the installed
# package metadata always matches this value — no duplication, no drift.
__version__ = "0.2.0"

# Library-level NullHandler — prevents "No handlers could be found" warnings.
# Users must configure logging themselves to see SDK log output.
import logging as _logging

_logging.getLogger("covia").addHandler(_logging.NullHandler())

__all__ = [
    "__version__",
    # Core classes
    "Grid",
    "Venue",
    "Job",
    "Asset",
    "JobStatus",
    # Managers
    "AgentManager",
    "SecretManager",
    "UCANManager",
    "WorkspaceManager",
    # Auth
    "Auth",
    "NoAuth",
    "BearerAuth",
    "BasicAuth",
    "Ed25519Auth",
    # DID / lattice paths
    "Namespace",
    "DIDURL",
    "did_url",
    "parse_did_url",
    "is_did",
    "did_method",
    "asset_hash",
    "did_web_to_url",
    "url_to_did_web",
    # Models
    "VenueStatus",
    "AssetList",
    "JobData",
    "DIDDocument",
    "MCPDiscovery",
    "AgentCard",
    "InvokeRequest",
    "OperationInfo",
    # Agent models
    "AgentCreateResult",
    "AgentRequestResult",
    "AgentMessageResult",
    "AgentChatResult",
    "AgentTriggerResult",
    "AgentQueryResult",
    "AgentListEntry",
    "AgentListResult",
    "AgentDeleteResult",
    "AgentSuspendResult",
    # Workspace models
    "WorkspaceReadResult",
    "WorkspaceWriteResult",
    "WorkspaceDeleteResult",
    "WorkspaceAppendResult",
    "WorkspaceListResult",
    "WorkspaceSliceResult",
    "WorkspaceInspectResult",
    "WorkspaceCountResult",
    "WorkspaceAggregateResult",
    "GroupCount",
    # UCAN + Secret models
    "UCANAttenuation",
    "UCANIssueResult",
    "SecretSetResult",
    "SecretExtractResult",
    # Exceptions
    "CoviaError",
    "GridError",
    "CoviaConnectionError",
    "CoviaTimeoutError",
    "JobFailedError",
    "NotFoundError",
    "AssetNotFoundError",
    "JobNotFoundError",
]
