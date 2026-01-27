"""Run an operation on a venue and print the result.

Usage:
    python examples/run_operation.py
"""

from covia import Grid

with Grid.connect("https://venue-test.covia.ai") as venue:
    # run() invokes the operation and waits for the result in one call
    result = venue.run(
        "text-summarise",
        {
            "text": "Covia enables AI models, agents, and data to collaborate "
            "across organisational boundaries. It provides federated "
            "orchestration with built-in governance.",
            "max_length": 50,
        },
        timeout=30,
    )
    print("Summary:", result)
