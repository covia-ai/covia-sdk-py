"""Run an operation on a venue and print the result.

Uses the schema-infer operation, which derives a JSON Schema from an example value.

Usage:
    python examples/run_operation.py
"""

import os

from covia import Grid

VENUE_URL = os.environ.get("COVIA_VENUE_URL", "https://venue-4.covia.ai")

with Grid.connect(VENUE_URL) as venue:
    # run() invokes the operation and waits for the result in one call
    result = venue.run("v/ops/schema/infer", {"value": {"name": "Ada", "age": 36, "admin": True}}, timeout=10)
    print("Result:", result)
