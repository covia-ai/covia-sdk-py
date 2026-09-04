"""Discover venue capabilities: DID, MCP, and operations.

Usage:
    python examples/discovery.py
"""

import os

from covia import Grid

VENUE_URL = os.environ.get("COVIA_VENUE_URL", "https://venue-4.covia.ai")

with Grid.connect(VENUE_URL) as venue:
    # DID document (decentralised identity)
    did_doc = venue.did_document()
    print(f"DID:     {did_doc.id}")
    print(f"Context: {did_doc.context}")

    # MCP discovery (Model Context Protocol)
    mcp = venue.mcp_discovery()
    print(f"\nMCP version:  {mcp.mcp_version}")
    print(f"MCP endpoint: {mcp.endpoint}")
    print(f"Tools:        {mcp.tools_endpoint}")

    # Named operations
    ops = venue.list_operations()
    print(f"\n{len(ops)} operations available:")
    for op in ops:
        desc = f" — {op.description}" if op.description else ""
        print(f"  {op.name}{desc}")
