"""
Superseded. sentinel_agent_sdk's AgentRunner (see ../main.py) owns
consuming, retry, and DLQ routing directly -- agent authors do not write a
consumer handler. See ../agent.py for the actual business logic
(ResponseAgent.process()).
"""
