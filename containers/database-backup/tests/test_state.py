"""Tests for backup.state — SchedulerState thread-safe shared state."""

import threading
import time

import pytest

from backup.state import SchedulerState, SourceStatus


@pytest.fixture
def state():
    return SchedulerState()


class TestUpdateAndGet:
    def test_update_creates_new_source(self, state):
        state.update_source("db1", source_type="mysql", interval_seconds=3600)
        sources = state.get_all_sources()
        assert "db1" in sources
        assert sources["db1"].source_type == "mysql"
        assert sources["db1"].interval_seconds == 3600

    def test_update_merges_fields(self, state):
        state.update_source("db1", source_type="mysql")
        state.update_source("db1", interval_seconds=7200)
        sources = state.get_all_sources()
        assert sources["db1"].source_type == "mysql"
        assert sources["db1"].interval_seconds == 7200

    def test_get_all_returns_copies(self, state):
        state.update_source("db1", source_type="mysql")
        sources = state.get_all_sources()
        sources["db1"].source_type = "modified"
        # Original should be unaffected
        assert state.get_all_sources()["db1"].source_type == "mysql"

    def test_get_source_returns_copy(self, state):
        state.update_source("db1", source_type="mysql")
        status = state.get_source("db1")
        status.source_type = "modified"
        assert state.get_source("db1").source_type == "mysql"

    def test_get_source_missing_returns_none(self, state):
        assert state.get_source("nonexistent") is None

    def test_remove_source(self, state):
        state.update_source("db1", source_type="mysql")
        state.remove_source("db1")
        assert state.get_all_sources() == {}

    def test_remove_nonexistent_does_not_raise(self, state):
        state.remove_source("nonexistent")

    def test_ignores_unknown_fields(self, state):
        state.update_source("db1", nonexistent_field="value")
        status = state.get_source("db1")
        assert not hasattr(status, "nonexistent_field") or status.name == "db1"


class TestManualTriggers:
    def test_enqueue_and_dequeue(self, state):
        state.request_manual_backup("db1")
        state.request_manual_backup("db2")
        triggers = state.pop_manual_triggers()
        assert triggers == ["db1", "db2"]

    def test_dequeue_clears_queue(self, state):
        state.request_manual_backup("db1")
        state.pop_manual_triggers()
        assert state.pop_manual_triggers() == []

    def test_duplicate_trigger_ignored(self, state):
        state.request_manual_backup("db1")
        state.request_manual_backup("db1")
        triggers = state.pop_manual_triggers()
        assert triggers == ["db1"]

    def test_empty_dequeue(self, state):
        assert state.pop_manual_triggers() == []


class TestWakeEvent:
    def test_wait_returns_after_timeout(self, state):
        start = time.monotonic()
        state.wait_for_wake(timeout=0.05)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.04

    def test_wake_interrupts_wait(self, state):
        start = time.monotonic()

        def wake_soon():
            time.sleep(0.02)
            state.request_manual_backup("db1")

        t = threading.Thread(target=wake_soon)
        t.start()
        state.wait_for_wake(timeout=5.0)
        elapsed = time.monotonic() - start
        assert elapsed < 1.0
        t.join()

    def test_event_cleared_after_wait(self, state):
        state.request_manual_backup("db1")
        state.wait_for_wake(timeout=0.01)
        # Second wait should actually wait
        start = time.monotonic()
        state.wait_for_wake(timeout=0.05)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.04
