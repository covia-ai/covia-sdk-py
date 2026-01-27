"""Resolve a named operation, then fetch and invoke its asset.

Usage:
    python examples/invoke_asset.py
"""

import os

from covia import Grid

VENUE_URL = os.environ.get("COVIA_VENUE_URL", "https://venue-test.covia.ai")

with Grid.connect(VENUE_URL) as venue:
    # Resolve an operation name to its asset ID
    op_info = venue.get_operation("test:echo")
    print(f"Operation: {op_info.name}  (asset: {op_info.asset})")

    # Fetch the asset and invoke it
    op = venue.get_asset(op_info.asset)
    print(f"  name: {op.name}")
    print(f"  is_operation: {op.is_operation}")
    result = op.run({"message": "invoked via asset"}, timeout=10)
    print(f"  result: {result}")
