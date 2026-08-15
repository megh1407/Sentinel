"""idempotency.py — Redis / in-memory response idempotency manager.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from sentinel_contracts.events.action_request_v1 import ActionRequestV1

logger = logging.getLogger(__name__)


class ResponseIdempotencyStore:
    """Ensures processing the same SystemRiskAssessment twice does NOT create duplicate actions."""

    def __init__(self, redis_client: Any | None = None) -> None:
        self._redis = redis_client
        self._memory_cache: dict[str, list[dict[str, Any]]] = {}

    def get_existing_actions(self, risk_id: str) -> list[ActionRequestV1] | None:
        key = f"sentinel:response:idempotency:{risk_id}"
        if self._redis:
            try:
                raw = self._redis.get(key)
                if raw:
                    data_list = json.loads(raw)
                    return [ActionRequestV1.model_validate(d) for d in data_list]
            except Exception as e:
                logger.warning("Redis read error in idempotency store: %s", e)

        if risk_id in self._memory_cache:
            return [ActionRequestV1.model_validate(d) for d in self._memory_cache[risk_id]]

        return None

    def save_actions(self, risk_id: str, actions: tuple[ActionRequestV1, ...], ttl_seconds: int = 3600) -> None:
        key = f"sentinel:response:idempotency:{risk_id}"
        dumped = [a.model_dump(mode="json") for a in actions]
        if self._redis:
            try:
                self._redis.setex(key, ttl_seconds, json.dumps(dumped))
            except Exception as e:
                logger.warning("Redis write error in idempotency store: %s", e)

        self._memory_cache[risk_id] = dumped
