"""The Risk Orchestrator's Domain Layer (Implementation Phase 2).

Pure business/domain modeling — entities, value objects, events,
commands, responses, enums, exceptions, validators, interfaces, and
constants. Contains zero infrastructure, zero I/O, and zero concrete
business logic (scoring formulas, rule evaluation, etc. are later
phases) — only the stable shapes every later phase depends on, per
Phase 3.1 §1.2/§3's domain/infrastructure boundary.

Sub-packages:
    constants   -- named numeric/string constants (no magic numbers).
    enums       -- closed, named vocabularies.
    exceptions  -- the SentinelException hierarchy (CSEGS §6.1).
    validators  -- reusable, composable validation functions.
    value_objects -- immutable, self-validating Value Objects.
    entities    -- identity-bearing domain entities and aggregates.
    events      -- domain/integration event contracts.
    commands    -- immutable command (request) contracts.
    responses   -- immutable internal response DTOs.
    interfaces  -- abstract repository and engine Protocols.
"""
