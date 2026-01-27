"""Connect to a Covia venue and check it's alive.

Usage:
    python examples/hello_venue.py
"""

from covia import Grid

VENUE_URL = "https://venue.covia.ai"

with Grid.connect(VENUE_URL) as venue:
    info = venue.status()
    print(f"Connected to {info.name}")
    print(f"URL: {info.url}")
    print(f"DID: {info.did}")
