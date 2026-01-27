"""Invoke an operation and track the job through its lifecycle.

Demonstrates invoke (non-blocking), polling, waiting, and cancellation.

Usage:
    python examples/job_lifecycle.py
"""

import os

from covia import Grid

VENUE_URL = os.environ.get("COVIA_VENUE_URL", "https://venue-test.covia.ai")

# Echo — returns input unchanged (completes quickly)
ECHO = "b8fc54e709ee295d97ffdba0ae446fe61782ba136f423cca469943955d818f33"
# Never — stays STARTED forever (useful for cancel demo)
NEVER = "dc7f887e781b3d352da3c6d353788f2ec7a36ef72f6b7cb1a34bb13bd8e631fe"

with Grid.connect(VENUE_URL) as venue:
    # invoke() returns immediately with a Job handle
    job = venue.invoke(ECHO, {"message": "hello"})
    print(f"Job {job.id} submitted  (status: {job.status})")

    # Poll manually
    job.refresh()
    print(f"After refresh: {job.status}")

    # Wait with timeout (blocks until terminal state)
    job.wait(timeout=10)
    print(f"Finished: {job.status}")

    if job.is_complete:
        print("Output:", job.output)
    else:
        print("Error:", job.error)

    # --- Cancel a job that never finishes ---
    stuck = venue.invoke(NEVER, {})
    print(f"\nNever-job {stuck.id} (status: {stuck.status})")
    stuck.cancel()
    print(f"After cancel: {stuck.status}")
