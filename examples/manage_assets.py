"""Register, upload, download, and browse assets.

Usage:
    python examples/manage_assets.py
"""

import json

from covia import Grid

with Grid.connect("https://venue.covia.ai") as venue:
    # Register a new asset with metadata
    asset_id = venue.register_asset(
        {
            "name": "customer-segments",
            "description": "Q4 customer segmentation results",
            "content-type": "application/json",
        }
    )
    print(f"Registered asset: {asset_id}")

    # Upload content
    payload = json.dumps({"segments": ["enterprise", "startup", "gov"]}).encode()
    content_hash = venue.put_asset_content(asset_id, payload)
    print(f"Uploaded content (hash: {content_hash})")

    # Retrieve the asset and inspect it
    asset = venue.get_asset(asset_id)
    print(f"Name:         {asset.name}")
    print(f"Content-Type: {asset.content_type}")
    print(f"Is operation: {asset.is_operation}")

    # Download content
    data = asset.get_content()
    print(f"Downloaded:   {json.loads(data)}")

    # List all assets
    listing = venue.list_assets(limit=10)
    print(f"\n{listing.total} assets on venue (showing first {len(listing.items)}):")
    for aid in listing.items:
        print(f"  - {aid}")
