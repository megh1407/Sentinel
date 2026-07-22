"""
in_memory_transport.py

A real, working message transport backed by in-process data structures --
not a mock. Used wherever a live Kafka broker isn't available (this
environment) or isn't wanted (fast unit tests). Semantics deliberately
mirror Kafka's pull model:

- produce() appends to a topic's append-only log and returns immediately.
- Each (group_id, topic) pair tracks its own read position, independent of
  other groups -- exactly like independent Kafka consumer groups.
- poll() advances the read position and returns the next unread message;
  commit() is a separate, explicit step (matching manual offset commit,
  Phase 1 Core Runtime Spec Part 4.2's commit-after-publish rule) that
  persists the position so a fresh consumer resuming the same group_id
  starts where the last one left off.
- pause()/resume() actually stop poll() from returning messages for the
  paused topics, proving EventConsumer's backpressure logic (Part 4.7)
  against real (if in-process) behavior.

Multiple topics are fully independent; a single logical "partition" per
topic is used (sufficient to prove SENTINEL's ordering-by-key requirement
in this environment, since we don't need multi-consumer partition
rebalancing to validate one agent's correctness).
"""
from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field

from .transport import Transport, TransportMessage

# Process-wide shared state so multiple InMemoryTransport instances (e.g. one
# producer, one consumer, in the same process) see the same topic logs --
# exactly like multiple clients pointed at the same real Kafka cluster.
_LOCK = threading.RLock()
_TOPIC_LOGS: dict[str, list[TransportMessage]] = defaultdict(list)
_GROUP_COMMITTED_OFFSET: dict[tuple[str, str], int] = {}  # (group_id, topic) -> committed offset (exclusive)
_GROUP_READ_POSITION: dict[tuple[str, str], int] = {}  # (group_id, topic) -> next position poll() will read


def reset_all_state() -> None:
    """Test-only helper: wipes every topic log and every consumer group's
    position. Never called from production code."""
    with _LOCK:
        _TOPIC_LOGS.clear()
        _GROUP_COMMITTED_OFFSET.clear()
        _GROUP_READ_POSITION.clear()


@dataclass
class InMemoryTransport:
    client_id: str
    _subscribed_topics: list[str] = field(default_factory=list)
    _group_id: str | None = None
    _paused_topics: set[str] = field(default_factory=set)
    _closed: bool = False

    def produce(self, message: TransportMessage) -> None:
        if self._closed:
            raise RuntimeError(f"transport {self.client_id} is closed")
        with _LOCK:
            offset = len(_TOPIC_LOGS[message.topic])
            message.offset = offset
            message.partition = 0
            _TOPIC_LOGS[message.topic].append(message)

    def subscribe(self, topics: list[str], group_id: str) -> None:
        self._subscribed_topics = list(topics)
        self._group_id = group_id
        with _LOCK:
            for topic in topics:
                key = (group_id, topic)
                if key not in _GROUP_COMMITTED_OFFSET:
                    _GROUP_COMMITTED_OFFSET[key] = 0
                if key not in _GROUP_READ_POSITION:
                    _GROUP_READ_POSITION[key] = _GROUP_COMMITTED_OFFSET[key]

    def poll(self, timeout_seconds: float) -> TransportMessage | None:
        if self._closed or not self._group_id:
            return None
        with _LOCK:
            for topic in self._subscribed_topics:
                if topic in self._paused_topics:
                    continue
                key = (self._group_id, topic)
                pos = _GROUP_READ_POSITION.get(key, 0)
                log = _TOPIC_LOGS[topic]
                if pos < len(log):
                    _GROUP_READ_POSITION[key] = pos + 1
                    return log[pos]
        return None

    def commit(self, message: TransportMessage) -> None:
        if not self._group_id:
            return
        with _LOCK:
            key = (self._group_id, message.topic)
            # Committed offset is "next offset to read on a fresh start" --
            # i.e. exclusive, matching real Kafka commit semantics.
            new_committed = (message.offset or 0) + 1
            if new_committed > _GROUP_COMMITTED_OFFSET.get(key, 0):
                _GROUP_COMMITTED_OFFSET[key] = new_committed

    def pause(self, topics: list[str] | None = None) -> None:
        self._paused_topics.update(topics or self._subscribed_topics)

    def resume(self, topics: list[str] | None = None) -> None:
        for t in (topics or list(self._paused_topics)):
            self._paused_topics.discard(t)

    def flush(self, timeout_seconds: float = 10.0) -> None:
        pass  # produce() is already synchronous in this transport

    def close(self) -> None:
        self._closed = True

    # -- test/diagnostic helpers, not part of the Transport protocol --
    def uncommitted_lag(self, topic: str) -> int:
        """Committed offset vs. log length -- mirrors Kafka consumer lag,
        used by tests proving retry/redelivery doesn't lose track of work."""
        with _LOCK:
            key = (self._group_id, topic)
            committed = _GROUP_COMMITTED_OFFSET.get(key, 0)
            return len(_TOPIC_LOGS[topic]) - committed


def reset_group_read_position_to_committed(group_id: str, topic: str) -> None:
    """Simulates what happens when a consumer process crashes and restarts:
    its in-flight (uncommitted) read position is lost, and a fresh poll()
    resumes from the last COMMITTED offset, causing redelivery of anything
    read-but-not-committed. Used explicitly by the chaos test."""
    with _LOCK:
        key = (group_id, topic)
        _GROUP_READ_POSITION[key] = _GROUP_COMMITTED_OFFSET.get(key, 0)
