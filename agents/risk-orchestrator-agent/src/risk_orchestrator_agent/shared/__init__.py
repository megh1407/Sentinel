"""Framework-independent shared utilities for the Risk Orchestrator.

Sub-packages:
    serialization -- the `Serializable` mixin used by every domain object.
    typing        -- shared type aliases.
    utilities     -- small helpers (time, id generation).

Nothing in this package may import from `domain/`, `memory/`, or
`handlers/` (Coding Standards §3.2) — it sits below the domain layer,
not beside it.
"""
