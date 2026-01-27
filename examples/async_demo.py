"""Full async workflow using AsyncGrid.

Usage:
    python examples/async_demo.py
"""

import asyncio
import os

from covia.async_api import AsyncGrid

VENUE_URL = os.environ.get("COVIA_VENUE_URL", "https://venue-test.covia.ai")

ECHO = "b8fc54e709ee295d97ffdba0ae446fe61782ba136f423cca469943955d818f33"


async def main() -> None:
    async with AsyncGrid.connect(VENUE_URL) as venue:
        # Check venue status
        status = await venue.status()
        print(f"Connected to {status.name}")

        # Run an operation (invoke + wait)
        result = await venue.run(ECHO, {"message": "hello async"}, timeout=10)
        print(f"Echo result: {result}")

        # Fire-and-forget with a job handle
        job = await venue.invoke(ECHO, {"message": "via job handle"})
        output = await job.result(timeout=10)
        print(f"Job result:  {output}")

        # List assets
        assets = await venue.list_assets(limit=5)
        print(f"\n{assets.total} assets on venue")


asyncio.run(main())
