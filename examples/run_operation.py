"""Run an operation on a venue and print the result.

Uses the Echo operation, which returns its input unchanged.

Usage:
    python examples/run_operation.py
"""

import os

from covia import Grid

VENUE_URL = os.environ.get("COVIA_VENUE_URL", "https://venue-test.covia.ai")

# Echo Operation — returns input unchanged
ECHO = "b8fc54e709ee295d97ffdba0ae446fe61782ba136f423cca469943955d818f33"

with Grid.connect(VENUE_URL) as venue:
    # run() invokes the operation and waits for the result in one call
    result = venue.run(ECHO, {"message": "Hello from Covia!"}, timeout=10)
    print("Result:", result)
