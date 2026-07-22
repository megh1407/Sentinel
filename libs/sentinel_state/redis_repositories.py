"""
redis_repositories.py

Real Redis repositories, tested against an actual live Redis instance
(this environment's redis-server). Mirrors the key-naming and TTL patterns
from the Phase 1 Core Runtime spec Part 5.1: `sentinel:{domain}:{entity}:{id}`.
"""
from __future__ import annotations

import json
from typing import TypeVar

import redis
from pydantic import BaseModel
from sentinel_common.errors import StateError

T = TypeVar("T", bound=BaseModel)


class RedisRepository:
    key_prefix: str = "base"

    def __init__(self, client: redis.Redis):
        self._client = client

    def _key(self, *parts: str) -> str:
        return f"sentinel:{self.key_prefix}:{':'.join(str(p) for p in parts)}"

    def _get_model(self, key: str, model_cls: type[T]) -> T | None:
        try:
            raw = self._client.get(key)
        except redis.RedisError as e:
            raise StateError(f"Redis GET failed for {key}: {e}") from e
        if raw is None:
            return None
        return model_cls.model_validate_json(raw)

    def _set_model(self, key: str, model: BaseModel, ttl_seconds: int) -> None:
        try:
            self._client.set(key, model.model_dump_json(), ex=ttl_seconds)
        except redis.RedisError as e:
            raise StateError(f"Redis SET failed for {key}: {e}") from e


class ZoneStateRepository(RedisRepository):
    key_prefix = "zone:state"

    def get(self, zone_id: str, model_cls: type[T]) -> T | None:
        return self._get_model(self._key(zone_id), model_cls)

    def set(self, zone_id: str, state: BaseModel, ttl_seconds: int = 120) -> None:
        self._set_model(self._key(zone_id), state, ttl_seconds)

    def invalidate(self, zone_id: str) -> None:
        try:
            self._client.delete(self._key(zone_id))
        except redis.RedisError as e:
            raise StateError(f"Redis DEL failed for {zone_id}: {e}") from e


class WorkerPresenceRepository(RedisRepository):
    key_prefix = "worker:presence"

    def get_zone_occupancy(self, zone_id: str) -> set[str]:
        try:
            return {m.decode() if isinstance(m, bytes) else m for m in self._client.smembers(self._key(zone_id))}
        except redis.RedisError as e:
            raise StateError(f"Redis SMEMBERS failed for {zone_id}: {e}") from e

    def add_presence(self, zone_id: str, worker_id: str, ttl_seconds: int = 43200) -> None:
        key = self._key(zone_id)
        try:
            pipe = self._client.pipeline()
            pipe.sadd(key, worker_id)
            pipe.expire(key, ttl_seconds)
            pipe.execute()
        except redis.RedisError as e:
            raise StateError(f"Redis SADD failed for {zone_id}: {e}") from e

    def remove_presence(self, zone_id: str, worker_id: str) -> None:
        try:
            self._client.srem(self._key(zone_id), worker_id)
        except redis.RedisError as e:
            raise StateError(f"Redis SREM failed for {zone_id}: {e}") from e


class HelloStateRepository(RedisRepository):
    """The trivial repository HelloAgent uses -- proves the whole
    self.state.hello.mark_seen() pattern end-to-end with real Redis."""
    key_prefix = "hello:seen"

    def mark_seen(self, event_id: str) -> None:
        try:
            self._client.set(self._key(str(event_id)), "1", ex=3600)
        except redis.RedisError as e:
            raise StateError(f"Redis SET failed for hello:seen {event_id}: {e}") from e

    def was_seen(self, event_id: str) -> bool:
        try:
            return self._client.exists(self._key(str(event_id))) == 1
        except redis.RedisError as e:
            raise StateError(f"Redis EXISTS failed for hello:seen {event_id}: {e}") from e


class WindowedCountRepository(RedisRepository):
    """Base for 'how many distinct X happened in the last N seconds' trackers, using
    a Redis sorted set (score = unix timestamp, member = X's id). Subclasses set
    key_prefix and can expose their own domain-named method (e.g. record_incident)
    as a thin wrapper around record(), for call-site readability.

    NOTE: Redis-only. Postgres's zone_history/anomalies tables (spec Part 7) would
    give durable history beyond Redis's TTL horizon -- not built yet.
    """

    def record(self, zone_id: str, member_id: str, timestamp: float, max_window_seconds: int = 604800) -> None:
        key = self._key(zone_id)
        try:
            pipe = self._client.pipeline()
            pipe.zadd(key, {member_id: timestamp})
            pipe.zremrangebyscore(key, 0, timestamp - max_window_seconds)
            pipe.expire(key, max_window_seconds)
            pipe.execute()
        except redis.RedisError as e:
            raise StateError(f"Redis ZADD failed for {self.key_prefix} {zone_id}: {e}") from e

    def count_recent(self, zone_id: str, window_seconds: int, now: float) -> int:
        try:
            return self._client.zcount(self._key(zone_id), now - window_seconds, now)
        except redis.RedisError as e:
            raise StateError(f"Redis ZCOUNT failed for {self.key_prefix} {zone_id}: {e}") from e


class IncidentTrackingRepository(WindowedCountRepository):
    """Windowed incident counting per zone. 'Too many incidents' means 'in the
    last N seconds', not 'ever', which is why this is a sorted set and not a
    plain counter."""
    key_prefix = "zone:incidents"

    def record_incident(self, zone_id: str, incident_id: str, timestamp: float,
                         max_window_seconds: int = 604800) -> None:
        self.record(zone_id, incident_id, timestamp, max_window_seconds)


class AnomalyTrackingRepository(WindowedCountRepository):
    """Windowed anomaly-occurrence counting per zone, for the 'repeated anomalies'
    meta-rule -- a zone firing many anomalies (of any type) in a short window is
    itself a signal, on top of whatever each individual anomaly already meant."""
    key_prefix = "zone:anomaly_occurrences"

    def record_anomaly(self, zone_id: str, anomaly_event_id: str, timestamp: float,
                        max_window_seconds: int = 604800) -> None:
        self.record(zone_id, anomaly_event_id, timestamp, max_window_seconds)


class StateChangeTrackingRepository(WindowedCountRepository):
    """Windowed ZoneState-update counting per zone, for the 'rapid state changes'
    rule -- a zone whose state keeps changing in a short window (thrashing
    occupancy, flapping sensors, etc.) may indicate instability worth flagging on
    its own, independent of whether any single change looked anomalous."""
    key_prefix = "zone:state_changes"

    def record_state_change(self, zone_id: str, zone_state_event_id: str, timestamp: float,
                             max_window_seconds: int = 604800) -> None:
        self.record(zone_id, zone_state_event_id, timestamp, max_window_seconds)


class ResponseTrackingRepository(RedisRepository):
    """response_agent's own private working memory -- never a wire format,
    never read by another agent. Backs services/response_service.py's
    idempotency (dedupe on event_id), rapid-escalation velocity detection
    (previous risk score per zone), active-response/escalation memory (so
    an unchanged severity for an already-active response doesn't re-fire
    duplicate actions), and action provenance (action_id -> originating
    risk_id/zone_id, so a later ActionResult failure can be escalated back
    to the right risk without guessing).

    Plain dict/JSON storage rather than `_get_model`/`_set_model`'s typed
    Pydantic path -- these records are this agent's own internal bookkeeping,
    not a registered wire contract, so a fixed schema would be the wrong fit.
    """
    key_prefix = "response"

    # -- event dedupe (at-least-once Kafka delivery) --
    def was_event_processed(self, event_id: str) -> bool:
        try:
            return self._client.exists(self._key("seen", event_id)) == 1
        except redis.RedisError as e:
            raise StateError(f"Redis EXISTS failed for response:seen {event_id}: {e}") from e

    def mark_event_processed(self, event_id: str, ttl_seconds: int = 86400) -> None:
        try:
            self._client.set(self._key("seen", event_id), "1", ex=ttl_seconds)
        except redis.RedisError as e:
            raise StateError(f"Redis SET failed for response:seen {event_id}: {e}") from e

    # -- previous-risk-per-zone (rapid-escalation velocity detection) --
    def get_previous_risk(self, zone_id: str) -> dict | None:
        try:
            raw = self._client.get(self._key("prev_risk", zone_id))
        except redis.RedisError as e:
            raise StateError(f"Redis GET failed for response:prev_risk {zone_id}: {e}") from e
        return json.loads(raw) if raw is not None else None

    def set_previous_risk(self, zone_id: str, *, score: float, risk_level: str, observed_at: str,
                           ttl_seconds: int = 3600) -> None:
        record = {"score": score, "risk_level": risk_level, "observed_at": observed_at}
        try:
            self._client.set(self._key("prev_risk", zone_id), json.dumps(record), ex=ttl_seconds)
        except redis.RedisError as e:
            raise StateError(f"Redis SET failed for response:prev_risk {zone_id}: {e}") from e

    # -- active-response state (duplicate/escalation suppression) --
    def get_active_response(self, risk_id: str) -> dict | None:
        try:
            raw = self._client.get(self._key("active", risk_id))
        except redis.RedisError as e:
            raise StateError(f"Redis GET failed for response:active {risk_id}: {e}") from e
        return json.loads(raw) if raw is not None else None

    def set_active_response(self, risk_id: str, record: dict, ttl_seconds: int = 86400) -> None:
        try:
            self._client.set(self._key("active", risk_id), json.dumps(record), ex=ttl_seconds)
        except redis.RedisError as e:
            raise StateError(f"Redis SET failed for response:active {risk_id}: {e}") from e

    def clear_active_response(self, risk_id: str) -> None:
        try:
            self._client.delete(self._key("active", risk_id))
        except redis.RedisError as e:
            raise StateError(f"Redis DEL failed for response:active {risk_id}: {e}") from e

    # -- action_id -> originating-risk provenance (ActionResult escalation) --
    def get_action_meta(self, action_id: str) -> dict | None:
        try:
            raw = self._client.get(self._key("action_meta", action_id))
        except redis.RedisError as e:
            raise StateError(f"Redis GET failed for response:action_meta {action_id}: {e}") from e
        return json.loads(raw) if raw is not None else None

    def set_action_meta(self, action_id: str, meta: dict, ttl_seconds: int = 86400) -> None:
        try:
            self._client.set(self._key("action_meta", action_id), json.dumps(meta), ex=ttl_seconds)
        except redis.RedisError as e:
            raise StateError(f"Redis SET failed for response:action_meta {action_id}: {e}") from e
