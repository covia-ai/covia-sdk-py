"""Tests for JobStatus enum."""

from __future__ import annotations

from covia.status import JobStatus


class TestJobStatus:
    def test_values(self):
        assert JobStatus.PENDING == "PENDING"
        assert JobStatus.STARTED == "STARTED"
        assert JobStatus.COMPLETE == "COMPLETE"
        assert JobStatus.FAILED == "FAILED"
        assert JobStatus.CANCELLED == "CANCELLED"
        assert JobStatus.REJECTED == "REJECTED"
        assert JobStatus.TIMEOUT == "TIMEOUT"
        assert JobStatus.INPUT_REQUIRED == "INPUT_REQUIRED"
        assert JobStatus.AUTH_REQUIRED == "AUTH_REQUIRED"
        assert JobStatus.PAUSED == "PAUSED"

    def test_finished_statuses(self):
        finished = {
            JobStatus.COMPLETE,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.REJECTED,
            JobStatus.TIMEOUT,
        }
        for s in finished:
            assert s.is_finished, f"{s} should be finished"

    def test_not_finished_statuses(self):
        not_finished = {
            JobStatus.PENDING,
            JobStatus.STARTED,
            JobStatus.PAUSED,
            JobStatus.INPUT_REQUIRED,
            JobStatus.AUTH_REQUIRED,
        }
        for s in not_finished:
            assert not s.is_finished, f"{s} should not be finished"

    def test_paused_statuses(self):
        paused = {
            JobStatus.PAUSED,
            JobStatus.INPUT_REQUIRED,
            JobStatus.AUTH_REQUIRED,
        }
        for s in paused:
            assert s.is_paused, f"{s} should be paused"

    def test_not_paused_statuses(self):
        not_paused = {
            JobStatus.PENDING,
            JobStatus.STARTED,
            JobStatus.COMPLETE,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.REJECTED,
            JobStatus.TIMEOUT,
        }
        for s in not_paused:
            assert not s.is_paused, f"{s} should not be paused"

    def test_string_comparison(self):
        """JobStatus values compare directly with plain strings."""
        assert JobStatus.COMPLETE == "COMPLETE"
        assert JobStatus("FAILED") == JobStatus.FAILED
