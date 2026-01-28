"""Covia Python SDK — federated AI orchestration grid client.

Connect to a Covia venue and invoke operations::

    from covia import Grid

    with Grid.connect("https://venue.covia.ai") as venue:
        result = venue.run("my-operation", {"prompt": "hello"})
"""

from covia.asset import Asset
from covia.auth import Auth, BasicAuth, BearerAuth, NoAuth
from covia.exceptions import (
    AssetNotFoundError,
    CoviaAPIError,
    CoviaConnectionError,
    CoviaError,
    CoviaTimeoutError,
    JobFailedError,
    JobNotFoundError,
)
from covia.grid import Grid
from covia.job import Job
from covia.models import (
    AgentCard,
    AssetList,
    DIDDocument,
    InvokeRequest,
    JobData,
    MCPDiscovery,
    OperationInfo,
    VenueStatus,
)
from covia.status import JobStatus
from covia.venue import Venue

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Core classes
    "Grid",
    "Venue",
    "Job",
    "Asset",
    "JobStatus",
    # Auth
    "Auth",
    "NoAuth",
    "BearerAuth",
    "BasicAuth",
    # Models
    "VenueStatus",
    "AssetList",
    "JobData",
    "DIDDocument",
    "MCPDiscovery",
    "AgentCard",
    "InvokeRequest",
    "OperationInfo",
    # Exceptions
    "CoviaError",
    "CoviaAPIError",
    "CoviaConnectionError",
    "CoviaTimeoutError",
    "JobFailedError",
    "AssetNotFoundError",
    "JobNotFoundError",
]
