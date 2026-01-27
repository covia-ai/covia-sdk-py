"""Discover venue capabilities: DID, MCP, and A2A agent card.

Usage:
    python examples/discovery.py
"""

from covia import Grid

with Grid.connect("https://venue.covia.ai") as venue:
    # DID document (decentralised identity)
    did_doc = venue.did_document()
    print(f"DID:     {did_doc.id}")
    print(f"Context: {did_doc.context}")

    # MCP discovery (Model Context Protocol)
    mcp = venue.mcp_discovery()
    print(f"\nMCP version:  {mcp.mcp_version}")
    print(f"MCP endpoint: {mcp.endpoint}")
    print(f"Tools:        {mcp.tools_endpoint}")

    # A2A agent card (Agent-to-Agent protocol)
    card = venue.agent_card()
    print(f"\nAgent provider:     {card.agentProvider}")
    print(f"Agent capabilities: {card.agentCapabilities}")
    print(f"Agent skills:       {card.agentSkills}")
