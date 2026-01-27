"""Fetch assets by ID — invoke an operation or download data.

Usage:
    python examples/invoke_asset.py
"""

import os

from covia import Grid

VENUE_URL = os.environ.get("COVIA_VENUE_URL", "https://venue-test.covia.ai")

# Echo Operation — an invocable asset
ECHO = "b8fc54e709ee295d97ffdba0ae446fe61782ba136f423cca469943955d818f33"
# Iris Dataset — a data asset (CSV)
IRIS = "8daf239fd79964c0a8a3171487f8b00bdfd224a5dcede5348c8c5832da1cca52"

with Grid.connect(VENUE_URL) as venue:
    # Invoke an operation asset
    op = venue.get_asset(ECHO)
    print(f"Asset: {op.name}")
    print(f"  is_operation: {op.is_operation}")
    result = op.run({"message": "invoked via asset"}, timeout=10)
    print(f"  result: {result}")

    # Download a data asset
    data = venue.get_asset(IRIS)
    print(f"\nAsset: {data.name}")
    print(f"  is_operation: {data.is_operation}")
    content = data.get_content()
    print(f"  size: {len(content)} bytes")
    print(f"  first line: {content.splitlines()[0].decode()}")
