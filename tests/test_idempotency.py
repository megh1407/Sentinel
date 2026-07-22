"""
test_idempotency.py

Proves the @idempotent decorator actually prevents a duplicate event_id
from re-running the wrapped handler's side effects -- a real redelivery
scenario, not just a description of the intended behavior.
"""
import uuid

from sentinel_eventbus.idempotency import InMemoryDedupeStore, idempotent


def test_idempotent_decorator_skips_known_duplicate():
    store = InMemoryDedupeStore()
    call_log = []

    class FakeEvent:
        def __init__(self, event_id):
            self.event_id = event_id

    @idempotent(store, ttl_seconds=60)
    def handler(event):
        call_log.append(event.event_id)
        return "processed"

    event_id = str(uuid.uuid4())
    event = FakeEvent(event_id)

    first_result = handler(event)
    second_result = handler(event)  # simulated redelivery of the SAME event_id

    assert first_result == "processed"
    assert second_result is None  # short-circuited, handler body did NOT run again
    assert call_log == [event_id]  # handler body only actually executed once


def test_idempotent_decorator_processes_distinct_event_ids_independently():
    store = InMemoryDedupeStore()
    call_log = []

    class FakeEvent:
        def __init__(self, event_id):
            self.event_id = event_id

    @idempotent(store, ttl_seconds=60)
    def handler(event):
        call_log.append(event.event_id)
        return "processed"

    e1, e2 = str(uuid.uuid4()), str(uuid.uuid4())
    handler(FakeEvent(e1))
    handler(FakeEvent(e2))

    assert call_log == [e1, e2]


def test_dedupe_store_ttl_expiry_allows_reprocessing_after_expiry():
    store = InMemoryDedupeStore()
    key = "idempotency:some-event-id"

    store.mark_seen(key, ttl_seconds=0)  # already-expired TTL
    import time
    time.sleep(0.01)
    assert store.seen(key) is False  # expired, so no longer considered a duplicate
