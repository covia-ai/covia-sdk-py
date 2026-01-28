"""Register, upload, download, and browse assets.

Usage:
    python examples/manage_assets.py
"""

import hashlib
import json
import os

from covia import Asset, Grid

VENUE_URL = os.environ.get("COVIA_VENUE_URL", "https://venue-test.covia.ai")

with Grid.connect(VENUE_URL) as venue:
    # Prepare content and compute its SHA-256 hash (content-addressed storage)
    payload = json.dumps({"segments": ["enterprise", "startup", "gov"]}).encode()
    content_hash = hashlib.sha256(payload).hexdigest().upper()

    # Register a new asset
    asset = venue.register(
        Asset(
            {
                "name": "customer-segments",
                "description": "Q4 customer segmentation results",
                "content": {
                    "contentType": "application/json",
                    "sha256": content_hash,
                },
            }
        )
    )
    print(f"Registered asset: {asset.id}")
    print(f"Name:         {asset.name}")
    print(f"Is operation: {asset.is_operation}")

    # Upload content
    asset.put_content(payload)
    print(f"Uploaded {len(payload)} bytes (sha256: {content_hash})")

    # Download content
    data = asset.get_content()
    print(f"Downloaded:   {json.loads(data)}")

    # List all assets
    listing = venue.list_assets(limit=10)
    print(f"\n{listing.total} assets on venue (showing first {len(listing.items)}):")
    for aid in listing.items:
        print(f"  - {aid}")
