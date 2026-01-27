"""Register, upload, download, and browse assets.

Usage:
    python examples/manage_assets.py
"""

import hashlib
import json
import os

from covia import Grid

VENUE_URL = os.environ.get("COVIA_VENUE_URL", "https://venue-test.covia.ai")

with Grid.connect(VENUE_URL) as venue:
    # Prepare content and compute its SHA-256 hash (content-addressed storage)
    payload = json.dumps({"segments": ["enterprise", "startup", "gov"]}).encode()
    content_hash = hashlib.sha256(payload).hexdigest().upper()

    # Register a new asset with metadata (hash must be included)
    asset_id = venue.register_asset(
        {
            "name": "customer-segments",
            "description": "Q4 customer segmentation results",
            "content": {
                "contentType": "application/json",
                "sha256": content_hash,
            },
        }
    )
    print(f"Registered asset: {asset_id}")

    # Upload content
    venue.put_asset_content(asset_id, payload)
    print(f"Uploaded {len(payload)} bytes (sha256: {content_hash})")

    # Retrieve the asset and inspect it
    asset = venue.get_asset(asset_id)
    print(f"Name:         {asset.name}")
    print(f"Is operation: {asset.is_operation}")

    # Download content
    data = asset.get_content()
    print(f"Downloaded:   {json.loads(data)}")

    # List all assets
    listing = venue.list_assets(limit=10)
    print(f"\n{listing.total} assets on venue (showing first {len(listing.items)}):")
    for aid in listing.items:
        print(f"  - {aid}")
