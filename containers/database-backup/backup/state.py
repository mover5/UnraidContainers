"""Thread-safe shared state between the scheduler and web GUI."""

import threading
import time
from dataclasses import dataclass, field


@dataclass
class SourceStatus:
    source_type: str = ""
    name: str = ""
    interval_seconds: float = 0
    retention_count: int = 0
    last_backup_monotonic: float | None = None
    last_backup_wall: float | None = None
    is_running: bool = False
    last_error: str | None = None


class SchedulerState:
    """Thread-safe state shared between the scheduler thread and the Flask app."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sources: dict[str, SourceStatus] = {}
        self._manual_triggers: list[str] = []
        self._wake_event = threading.Event()

    def update_source(self, name: str, **kwargs) -> None:
        with self._lock:
            if name not in self._sources:
                self._sources[name] = SourceStatus(name=name)
            status = self._sources[name]
            for k, v in kwargs.items():
                if hasattr(status, k):
                    setattr(status, k, v)

    def get_all_sources(self) -> dict[str, SourceStatus]:
        with self._lock:
            return {
                name: SourceStatus(**vars(status))
                for name, status in self._sources.items()
            }

    def get_source(self, name: str) -> SourceStatus | None:
        with self._lock:
            status = self._sources.get(name)
            if status is None:
                return None
            return SourceStatus(**vars(status))

    def remove_source(self, name: str) -> None:
        with self._lock:
            self._sources.pop(name, None)

    def request_manual_backup(self, name: str) -> None:
        with self._lock:
            if name not in self._manual_triggers:
                self._manual_triggers.append(name)
        self._wake_event.set()

    def pop_manual_triggers(self) -> list[str]:
        with self._lock:
            triggers = list(self._manual_triggers)
            self._manual_triggers.clear()
            return triggers

    def wait_for_wake(self, timeout: float) -> None:
        self._wake_event.wait(timeout=timeout)
        self._wake_event.clear()


shared_state = SchedulerState()
