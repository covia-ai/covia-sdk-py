"""Fetch an operation asset and invoke it directly.

Usage:
    python examples/invoke_asset.py
"""

from covia import Grid

with Grid.connect("https://venue.covia.ai") as venue:
    # Look up an operation asset by ID
    op = venue.get_asset("abc123def456...")
    print(f"Asset: {op.name}")
    print(f"Description: {op.description}")

    if op.is_operation:
        # run() invokes and waits for the result
        result = op.run({"prompt": "What is lattice consensus?"}, timeout=30)
        print("Result:", result)
    else:
        # It's a data asset -- download it instead
        content = op.get_content()
        print(f"Downloaded {len(content)} bytes")
