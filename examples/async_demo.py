"""Full async workflow using AsyncGrid.

Usage:
    python examples/async_demo.py
"""

import asyncio
import os

from covia.async_api import AsyncGrid

VENUE_URL = os.environ.get("COVIA_VENUE_URL", "https://venue-test.covia.ai")


async def main() -> None:
    async with AsyncGrid.connect(VENUE_URL) as venue:
        # Check venue status
        status = await venue.status()
        print(f"Connected to {status.name}")

        # Run an operation (invoke + wait)
        result = await venue.run("test:echo", {"message": "hello async"}, timeout=10)
        print(f"Echo result: {result}")

        # Fire-and-forget with a job handle
        job = await venue.invoke("test:echo", {"message": "via job handle"})
        output = await job.result(timeout=10)
        print(f"Job result:  {output}")

        # List available operations
        ops = await venue.list_operations()
        print(f"\n{len(ops)} operations available:")
        for op in ops[:5]:
            print(f"  {op.name} ({op.asset[:16]}...)")


asyncio.run(main())
