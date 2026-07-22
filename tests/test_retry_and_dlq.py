"""
test_retry_and_dlq.py

Proves RetryRouter's classification and topic-routing logic for real: a
RetryableError routes to `{topic}.retry` with an incrementing retry_count
and a computed backoff, up to max_attempts, after which it routes to
`{topic}.dlq` with full failure metadata. A FatalError routes to DLQ
immediately, on the first failure, no retries wasted.
"""
from sentinel_common.errors import FatalError, RetryableError
from sentinel_eventbus import InMemoryTransport
from sentinel_eventbus.retry import (
    HEADER_ERROR_TYPE,
    HEADER_ORIGINAL_TOPIC,
    HEADER_RETRY_AFTER,
    HEADER_RETRY_COUNT,
    RetryPolicy,
    RetryRouter,
)
from sentinel_eventbus.transport import TransportMessage


def test_retryable_error_routes_to_retry_topic_with_incrementing_count():
    transport = InMemoryTransport(client_id="t1")
    router = RetryRouter(transport, RetryPolicy(max_attempts=3))

    original = TransportMessage(topic="sensor.events.raw", key="Z-104", value=b"payload", headers={HEADER_RETRY_COUNT: "0"})
    destination = router.route_failure(original, RetryableError("db timeout"), consumer_group="test-group")

    assert destination == "sensor.events.raw.retry"
    from sentinel_eventbus import in_memory_transport as imt
    retried = imt._TOPIC_LOGS["sensor.events.raw.retry"][0]
    assert retried.headers[HEADER_RETRY_COUNT] == "1"
    assert retried.headers[HEADER_ORIGINAL_TOPIC] == "sensor.events.raw"
    assert float(retried.headers[HEADER_RETRY_AFTER]) > 0


def test_retryable_error_exhausts_to_dlq_after_max_attempts():
    transport = InMemoryTransport(client_id="t1")
    policy = RetryPolicy(max_attempts=2, backoff_schedule_seconds=[0, 0])
    router = RetryRouter(transport, policy)

    msg = TransportMessage(topic="sensor.events.raw", key="Z-104", value=b"payload", headers={HEADER_RETRY_COUNT: "0"})

    dest1 = router.route_failure(msg, RetryableError("timeout 1"), "test-group")
    assert dest1 == "sensor.events.raw.retry"

    # simulate the retry-topic consumer reading it back and failing again
    from sentinel_eventbus import in_memory_transport as imt
    retried_log = imt._TOPIC_LOGS["sensor.events.raw.retry"]
    assert len(retried_log) == 1
    retried_msg = retried_log[0]
    assert retried_msg.headers[HEADER_RETRY_COUNT] == "1"

    dest2 = router.route_failure(retried_msg, RetryableError("timeout 2"), "test-group")
    assert dest2 == "sensor.events.raw.retry"

    retried_log_2 = imt._TOPIC_LOGS["sensor.events.raw.retry"]
    retried_msg_2 = retried_log_2[1]
    assert retried_msg_2.headers[HEADER_RETRY_COUNT] == "2"

    dest3 = router.route_failure(retried_msg_2, RetryableError("timeout 3"), "test-group")
    assert dest3 == "sensor.events.raw.dlq"

    dlq_log = imt._TOPIC_LOGS["sensor.events.raw.dlq"]
    assert len(dlq_log) == 1
    assert dlq_log[0].headers[HEADER_ERROR_TYPE] == "RetryableError"
    assert dlq_log[0].headers[HEADER_ORIGINAL_TOPIC] == "sensor.events.raw"


def test_fatal_error_routes_directly_to_dlq_no_retry():
    transport = InMemoryTransport(client_id="t1")
    router = RetryRouter(transport, RetryPolicy(max_attempts=5))

    msg = TransportMessage(topic="sensor.events.raw", key="Z-104", value=b"payload", headers={HEADER_RETRY_COUNT: "0"})
    destination = router.route_failure(msg, FatalError("schema validation will never pass"), "test-group")

    assert destination == "sensor.events.raw.dlq"
    from sentinel_eventbus import in_memory_transport as imt
    dlq_log = imt._TOPIC_LOGS["sensor.events.raw.dlq"]
    assert dlq_log[0].headers[HEADER_ERROR_TYPE] == "FatalError"


def test_backoff_is_actually_enforced_before_redelivery():
    transport = InMemoryTransport(client_id="t1")
    policy = RetryPolicy(max_attempts=3, backoff_schedule_seconds=[100, 100, 100])  # long backoff
    router = RetryRouter(transport, policy)

    msg = TransportMessage(topic="t", key="k", value=b"v", headers={HEADER_RETRY_COUNT: "0"})
    router.route_failure(msg, RetryableError("slow"), "g")

    from sentinel_eventbus import in_memory_transport as imt
    retried = imt._TOPIC_LOGS["t.retry"][0]
    assert router.is_ready_for_redelivery(retried) is False  # 100s backoff hasn't elapsed
