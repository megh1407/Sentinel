"""
Superseded. sentinel_agent_sdk's AgentRunner (see ../main.py) publishes
whatever agent.process() returns -- there is no publish() API exposed to
agent authors (base_agent.py's module docstring: "this is what makes the
'no agent-to-agent calls, everything through Kafka' invariant structural").
See ../services/response_service.py for how the outbound ActionRequestV1
list is built.
"""
