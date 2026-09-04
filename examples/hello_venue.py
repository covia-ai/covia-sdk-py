"""Connect to a Covia venue and check it's alive.

Usage:
    COVIA_VENUE_URL=https://localhost:8080 python examples/hello_venue.py
"""

import os

from covia import Grid

VENUE_URL = os.environ.get("COVIA_VENUE_URL", "https://venue-4.covia.ai")

venue= Grid.connect(VENUE_URL)
info = venue.status()
print(f"Connected to {info.name}")
print(f"URL: {info.url}")
print(f"DID: {info.did}")
