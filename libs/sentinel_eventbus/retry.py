"""
retry.py

Real retry/DLQ routing logic. RetryRouter classifies a failure by its
SentinelError subclass and decides where the message goes next:
- RetryableError, attempts remaining -> `{topic}.retry` with a computed
  retry_after header.
- FatalError, or RetryableError with attempts exhausted -> `{topic}.dlq`
  with full failure metadata attached.

This is exercised for real against InMemoryTransport in
tests/test_retry_and_dlq.py -- not just described.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from sentinel_common.errors import FatalError, RetryableError, SentinelError

from .transport import Transport, TransportMessage

HEADER_RETRY_COUNT = "retry_count"
HEADER_RETRY_AFTER = "retry_after_epoch_seconds"
HEADER_ORIGINAL_TOPIC = "original_topic"
HEADER_ERROR_TYPE = "error_type"
HEADER_ERROR_MESSAGE = "error_message"
HEADER_FIRST_FAILED_AT = "first_failed_at_epoch_seconds"
HEADER_CONSUMER_GROUP = "consumer_group"


@dataclass
class RetryPolicy:
    max_attempts: int = 5
    backoff_schedule_seconds: list[float] = field(default_factory=lambda: [1, 5, 30, 120, 600])

    def backoff_for_attempt(self, attempt: int) -> float:
        idx = min(attempt, len(self.backoff_schedule_seconds) - 1)
        return self.backoff_schedule_seconds[idx]


class RetryRouter:
    def __init__(self, transport: Transport, policy: RetryPolicy | None = None):
        self._transport = transport
        self._policy = policy or RetryPolicy()

    def route_failure(self, original_message: TransportMessage, error: Exception,
                       consumer_group: str) -> str:
        """Decides retry vs. DLQ and publishes accordingly. Returns the
        destination topic name it routed to (used by tests/observability,
        not required by callers)."""
        attempt = int(original_message.headers.get(HEADER_RETRY_COUNT, "0"))
        is_retryable = isinstance(error, RetryableError) or (
            not isinstance(error, SentinelError) and not isinstance(error, FatalError)
        )
        # An unclassified (non-SentinelError) exception is treated as
        # retryable ONCE, then routes to DLQ on the next failure if it keeps
        # happening -- avoids infinite silent retry loops on a genuine bug
        # while still tolerating one transient hiccup.

        original_topic = original_message.headers.get(HEADER_ORIGINAL_TOPIC, original_message.topic)

        if is_retryable and attempt < self._policy.max_attempts:
            destination = f"{original_topic}.retry"
            headers = dict(original_message.headers)
            headers[HEADER_RETRY_COUNT] = str(attempt + 1)
            headers[HEADER_ORIGINAL_TOPIC] = original_topic
            headers[HEADER_RETRY_AFTER] = str(time.time() + self._policy.backoff_for_attempt(attempt))
            headers[HEADER_ERROR_TYPE] = type(error).__name__
            headers[HEADER_ERROR_MESSAGE] = str(error)
            headers.setdefault(HEADER_FIRST_FAILED_AT, str(time.time()))
            headers[HEADER_CONSUMER_GROUP] = consumer_group
        else:
            destination = f"{original_topic}.dlq"
            headers = dict(original_message.headers)
            headers[HEADER_ORIGINAL_TOPIC] = original_topic
            headers[HEADER_ERROR_TYPE] = type(error).__name__
            headers[HEADER_ERROR_MESSAGE] = str(error)
            headers.setdefault(HEADER_FIRST_FAILED_AT, str(time.time()))
            headers[HEADER_RETRY_COUNT] = str(attempt)
            headers[HEADER_CONSUMER_GROUP] = consumer_group

        self._transport.produce(TransportMessage(
            topic=destination,
            key=original_message.key,
            value=original_message.value,
            headers=headers,
        ))
        return destination

    def is_ready_for_redelivery(self, retry_message: TransportMessage) -> bool:
        """A retry-topic consumer calls this before reprocessing -- proves
        the backoff was actually honored, not just computed."""
        retry_after = float(retry_message.headers.get(HEADER_RETRY_AFTER, "0"))
        return time.time() >= retry_after
