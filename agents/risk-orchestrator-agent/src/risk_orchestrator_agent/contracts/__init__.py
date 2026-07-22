"""Contract-facing declarations local to the Risk Orchestrator agent.

Sub-packages:
    kafka     -- topic-name constants for this agent's registered contract.
    requests  -- (future) inbound wire-format DTOs.
    responses -- (future) outbound wire-format DTOs.
    schemas   -- (future) local schema helpers.

The schemas of record remain the repository-wide
`contracts/agent-contracts/v1/*.schema.json` files; nothing here
redefines them.
"""
