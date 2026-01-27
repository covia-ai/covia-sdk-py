"""Tests for Job lifecycle and status tracking."""

from __future__ import annotations

import pytest

from covia import Job, JobStatus
from covia.exceptions import CoviaTimeoutError, JobFailedError
from covia.models import JobData
from tests.conftest import VENUE_URL

API_BASE = f"{VENUE_URL}/api/v1/"


def _make_job(venue, **kwargs):
    """Create a Job with given JobData fields."""
    data = JobData(id="job001", status=JobStatus.PENDING, **kwargs)
    return Job(data=data, venue=venue)


class TestJobProperties:
    def test_id(self, venue):
        job = _make_job(venue)
        assert job.id == "job001"

    def test_status_pending(self, venue):
        job = _make_job(venue)
        assert job.status == JobStatus.PENDING
        assert not job.is_finished
        assert not job.is_complete
        assert not job.is_paused

    def test_status_complete(self, venue):
        data = JobData(id="j1", status=JobStatus.COMPLETE, output={"val": 1})
        job = Job(data=data, venue=venue)
        assert job.is_finished
        assert job.is_complete
        assert job.output == {"val": 1}

    def test_status_failed(self, venue):
        data = JobData(id="j2", status=JobStatus.FAILED, error="boom")
        job = Job(data=data, venue=venue)
        assert job.is_finished
        assert not job.is_complete
        assert job.error == "boom"

    def test_status_paused(self, venue):
        data = JobData(id="j3", status=JobStatus.INPUT_REQUIRED)
        job = Job(data=data, venue=venue)
        assert job.is_paused
        assert not job.is_finished

    def test_output_raises_if_not_finished(self, venue):
        job = _make_job(venue)
        with pytest.raises(ValueError, match="not finished"):
            _ = job.output

    def test_output_raises_if_failed(self, venue):
        data = JobData(id="j4", status=JobStatus.FAILED, error="oops")
        job = Job(data=data, venue=venue)
        with pytest.raises(JobFailedError, match="oops"):
            _ = job.output

    def test_repr(self, venue):
        job = _make_job(venue)
        r = repr(job)
        assert "job001" in r
        assert "PENDING" in r


class TestJobRefresh:
    def test_refresh_updates_status(self, httpx_mock, venue):
        job = _make_job(venue)
        httpx_mock.add_response(
            url=f"{API_BASE}jobs/job001",
            json={"id": "job001", "status": "STARTED"},
        )
        job.refresh()
        assert job.status == JobStatus.STARTED

    def test_refresh_no_id_raises(self, venue):
        data = JobData(status=JobStatus.PENDING)
        job = Job(data=data, venue=venue)
        with pytest.raises(ValueError, match="no ID"):
            job.refresh()


class TestJobWait:
    def test_wait_already_finished(self, venue):
        data = JobData(id="j1", status=JobStatus.COMPLETE, output="done")
        job = Job(data=data, venue=venue)
        job.wait()  # Should return immediately

    def test_wait_polls_until_complete(self, httpx_mock, venue):
        job = _make_job(venue)
        # First poll returns STARTED, second returns COMPLETE
        httpx_mock.add_response(
            url=f"{API_BASE}jobs/job001",
            json={"id": "job001", "status": "STARTED"},
        )
        httpx_mock.add_response(
            url=f"{API_BASE}jobs/job001",
            json={"id": "job001", "status": "COMPLETE", "output": "result"},
        )
        job.wait(timeout=10)
        assert job.is_complete
        assert job.output == "result"

    def test_wait_timeout_raises(self, httpx_mock, venue):
        job = _make_job(venue)
        # Always return STARTED so we time out
        httpx_mock.add_response(
            url=f"{API_BASE}jobs/job001",
            json={"id": "job001", "status": "STARTED"},
        )
        with pytest.raises(CoviaTimeoutError, match="did not finish"):
            job.wait(timeout=0.1)


class TestJobResult:
    def test_result_returns_output(self, httpx_mock, venue):
        data = JobData(id="j1", status=JobStatus.COMPLETE, output=42)
        job = Job(data=data, venue=venue)
        assert job.result() == 42

    def test_result_raises_on_failure(self, venue):
        data = JobData(id="j2", status=JobStatus.REJECTED, error="denied")
        job = Job(data=data, venue=venue)
        with pytest.raises(JobFailedError, match="denied"):
            job.result()


class TestJobCancel:
    def test_cancel(self, httpx_mock, venue):
        job = _make_job(venue)
        httpx_mock.add_response(
            url=f"{API_BASE}jobs/job001/cancel",
            json={"id": "job001", "status": "CANCELLED"},
        )
        job.cancel()
        assert job.status == JobStatus.CANCELLED

    def test_cancel_no_id_raises(self, venue):
        data = JobData(status=JobStatus.PENDING)
        job = Job(data=data, venue=venue)
        with pytest.raises(ValueError, match="no ID"):
            job.cancel()
