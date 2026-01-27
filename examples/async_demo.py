"""Full async workflow using AsyncGrid.

Usage:
    python examples/async_demo.py
"""

import asyncio

from covia.async_api import AsyncGrid


async def main() -> None:
    async with AsyncGrid.connect("https://venue.covia.ai") as venue:
        # Check venue status
        status = await venue.status()
        print(f"Connected to {status.name}")

        # Run an operation (invoke + wait)
        result = await venue.run(
            "text-summarise",
            {"text": "Covia is federated AI orchestration.", "max_length": 20},
            timeout=30,
        )
        print("Summary:", result)

        # Fire-and-forget with a job handle
        job = await venue.invoke("analyse", {"data": [1, 2, 3]})
        output = await job.result(timeout=60)
        print("Analysis:", output)

        # List assets
        assets = await venue.list_assets(limit=5)
        print(f"{assets.total} assets on venue")


asyncio.run(main())
