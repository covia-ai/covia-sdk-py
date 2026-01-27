"""Invoke an operation and track the job through its lifecycle.

Demonstrates invoke (non-blocking), polling, waiting, streaming,
and cancellation.

Usage:
    python examples/job_lifecycle.py
"""

from covia import Grid

with Grid.connect("https://venue.covia.ai") as venue:
    # invoke() returns immediately with a Job handle
    job = venue.invoke("long-running-analysis", {"dataset": "q4-sales"})
    print(f"Job {job.id} submitted  (status: {job.status})")

    # --- Option A: poll manually ---
    job.refresh()
    print(f"After refresh: {job.status}")

    # --- Option B: wait with timeout ---
    job.wait(timeout=120)
    print(f"Finished: {job.status}")

    if job.is_complete:
        print("Output:", job.output)
    else:
        print("Error:", job.error)

    # --- Option C: stream SSE events ---
    job2 = venue.invoke("streaming-op", {"query": "explain lattice consensus"})
    for event in job2.stream():
        print(f"[{event.event}] {event.data}")

    # --- Cancel a job ---
    job3 = venue.invoke("slow-op", {"n": 1_000_000})
    job3.cancel()
    print(f"Cancelled: {job3.status}")  # JobStatus.CANCELLED
