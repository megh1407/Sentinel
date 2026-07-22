"""
idempotency.py

Real idempotency enforcement. `event_id` (a UUIDv7) is checked against a
"recently processed" dedupe store before the wrapped handler runs; a known
duplicate short-circuits to a no-op. The dedupe store is pluggable
(DedupeStore protocol) -- production uses Redis (via sentinel_state),
tests use an in-process set. Both are real, working implementations, not
placeholders.
"""
from __future__ import annotations

import functools
import time
from typing import Protocol


class DedupeStore(Protocol):
    def seen(self, key: str) -> bool: ...
    def mark_seen(self, key: str, ttl_seconds: int) -> None: ...


class InMemoryDedupeStore:
    """Real, working dedupe store backed by a dict with TTL expiry checked
    on access. Used for local dev/tests; RedisDedupeStore (sentinel_state)
    is the production equivalent."""

    def __init__(self):
        self._store: dict[str, float] = {}  # key -> expiry epoch seconds

    def seen(self, key: str) -> bool:
        expiry = self._store.get(key)
        if expiry is None:
            return False
        if time.time() > expiry:
            del self._store[key]
            return False
        return True

    def mark_seen(self, key: str, ttl_seconds: int) -> None:
        self._store[key] = time.time() + ttl_seconds


def idempotent(store: DedupeStore, ttl_seconds: int = 24 * 3600):
    """Decorator factory: idempotent(store)(handler). Wraps a handler whose
    first positional argument (after self, if a method) is the event, and
    which exposes an `.event_id` attribute (every generated Pydantic event
    model does, per the BaseEvent envelope)."""

    def decorator(handler):
        @functools.wraps(handler)
        def wrapper(*args, **kwargs):
            # Support both `handler(event)` and `self.handler(event)` call shapes.
            event = args[-1] if args else kwargs.get("event")
            key = f"idempotency:{getattr(event, 'event_id', None)}"
            if store.seen(key):
                return None  # known duplicate -- safe no-op
            result = handler(*args, **kwargs)
            store.mark_seen(key, ttl_seconds)
            return result

        return wrapper

    return decorator
