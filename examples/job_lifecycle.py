"""Invoke an operation and track the job through its lifecycle.

Demonstrates invoke (non-blocking), polling, waiting, and cancellation.

Usage:
    python examples/job_lifecycle.py
"""

import os

from covia import Grid

VENUE_URL = os.environ.get("COVIA_VENUE_URL", "https://venue-test.covia.ai")

with Grid.connect(VENUE_URL) as venue:
    # invoke() returns immediately with a Job handle
    job = venue.invoke("v/ops/schema/infer", {"value": {"name": "Ada", "age": 36}})
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

    # --- Cancel a long-running job (v/test/ops/never deliberately never completes) ---
    stuck = venue.invoke("v/test/ops/never", {})
    print(f"\nNever-job {stuck.id} (status: {stuck.status})")
    stuck.cancel()
    print(f"After cancel: {stuck.status}")
