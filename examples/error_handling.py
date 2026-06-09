"""Graceful error handling for common failure modes.

Uses the Fail Operation, which always raises an error.

Usage:
    python examples/error_handling.py
"""

import os

from covia import (
    GridError,
    CoviaConnectionError,
    CoviaError,
    CoviaTimeoutError,
    Grid,
    JobFailedError,
)

VENUE_URL = os.environ.get("COVIA_VENUE_URL", "https://venue-test.covia.ai")

try:
    with Grid.connect(VENUE_URL) as venue:
        result = venue.run("v/test/ops/error", {"message": "something went wrong"}, timeout=10)
        print("Result:", result)

except JobFailedError as e:
    # The operation ran but finished in FAILED / CANCELLED / REJECTED / TIMEOUT
    print(f"Job {e.job_data.id} ended with {e.job_data.status}")
    print(f"Error detail: {e.job_data.error}")

except CoviaTimeoutError:
    # Polling exceeded the timeout we specified
    print("Timed out waiting for the operation to complete")

except GridError as e:
    # The venue returned an HTTP error (4xx / 5xx)
    print(f"API error {e.status_code}: {e.message}")

except CoviaConnectionError:
    # Network-level failure (DNS, TCP, TLS)
    print("Could not connect to the venue")

except CoviaError as e:
    # Catch-all for any other SDK error
    print(f"Unexpected SDK error: {e}")
