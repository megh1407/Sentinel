"""
agent.py

ResponseAgent -- the BaseAgent subclass. Per sentinel_agent_sdk's design,
this implements exactly process(); AgentRunner (main.py) owns consuming,
publishing, retries, metrics, and shutdown.

Boundary (verified against contracts/agent-registry/agents.yaml AND
contracts/topics/kafka_topics.yaml, not just one or the other -- see
README.md):

  consumes:
    - RiskScoreV1   (sentinel.risk.score.v1)   -- real, canonical, the only
      input agents.yaml originally declared for this agent.
    - ActionResultV1 (sentinel.action.result.v1) -- real, canonical.
      kafka_topics.yaml already listed response_agent as a consumer of this
      topic before this task (agents.yaml did not -- a pre-existing
      registry drift, fixed as part of this task, not a new addition this
      agent invents unilaterally). Needed for SS13/SS16/SS22's failed-
      action escalation behaviour (see services/response_service.py).

  produces:
    - ActionRequestV1 (sentinel.action.request.v1) -- real, canonical, the
      only output schema/topic this agent is registered to produce.
      ActionRequest v2 (the unrelated justification->explanation rename)
      is deliberately NOT dual-written here -- see README's PLATFORM_GAP
      note.

See README.md's "Contract changes made for this task" section for the new
OPTIONAL fields added to RiskScore v1 and ActionRequest v1 to support the
emergency-decision model (affected_zones, cascade_paths, priority,
emergency_triggered, etc.) -- all additive, non-breaking per
contracts/versioning/compatibility_rules.md.
"""
from __future__ import annotations

from pydantic import BaseModel
from sentinel_agent_sdk import BaseAgent
from sentinel_common.errors import ContractViolationError
from sentinel_contracts.events.action_request_v1 import ActionRequestV1
from sentinel_contracts.events.action_result_v1 import ActionResultV1
from sentinel_contracts.events.risk_score_v1 import RiskScoreV1

from response_agent.services.response_service import ResponseService


class ResponseAgent(BaseAgent):
    def initialize(self) -> None:
        response_repo = self.state.response if self.state is not None else None
        self._service = ResponseService(response_repo=response_repo, logger=self.logger)

    # -- BaseAgent contract: the one method every agent implements --
    def process(self, event: BaseModel) -> list[ActionRequestV1] | None:
        if isinstance(event, RiskScoreV1):
            return self._service.handle_risk_score(event)
        if isinstance(event, ActionResultV1):
            return self._service.handle_action_result(event)
        raise ContractViolationError(f"ResponseAgent received an unexpected event type: {type(event).__name__}")
