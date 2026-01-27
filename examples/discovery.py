"""Discover venue capabilities: DID and MCP.

Usage:
    python examples/discovery.py
"""

import os

from covia import Grid

VENUE_URL = os.environ.get("COVIA_VENUE_URL", "https://venue-test.covia.ai")

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
