"""Graceful error handling for common failure modes.

Usage:
    python examples/error_handling.py
"""

from covia import (
    CoviaAPIError,
    CoviaConnectionError,
    CoviaError,
    CoviaTimeoutError,
    Grid,
    JobFailedError,
)

try:
    with Grid.connect("https://venue.covia.ai") as venue:
        result = venue.run("might-fail", {"x": 1}, timeout=30)
        print("Result:", result)

except JobFailedError as e:
    # The operation ran but finished in FAILED / CANCELLED / REJECTED / TIMEOUT
    print(f"Job {e.job_data.id} ended with {e.job_data.status}")
    print(f"Error detail: {e.job_data.error}")

except CoviaTimeoutError:
    # Polling exceeded the timeout we specified
    print("Timed out waiting for the operation to complete")

except CoviaAPIError as e:
    # The venue returned an HTTP error (4xx / 5xx)
    print(f"API error {e.status_code}: {e.message}")

except CoviaConnectionError:
    # Network-level failure (DNS, TCP, TLS)
    print("Could not connect to the venue")

except CoviaError as e:
    # Catch-all for any other SDK error
    print(f"Unexpected SDK error: {e}")
