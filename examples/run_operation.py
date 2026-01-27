"""Run an operation on a venue and print the result.

Uses the Echo operation, which returns its input unchanged.

Usage:
    python examples/run_operation.py
"""

import os

from covia import Grid

VENUE_URL = os.environ.get("COVIA_VENUE_URL", "https://venue-test.covia.ai")

with Grid.connect(VENUE_URL) as venue:
    # run() invokes the operation and waits for the result in one call
    result = venue.run("test:echo", {"message": "Hello from Covia!"}, timeout=10)
    print("Result:", result)
