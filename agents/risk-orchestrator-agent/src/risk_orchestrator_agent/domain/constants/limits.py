"""Shared constants for the domain layer.

Every magic number or magic string a validator or domain object needs is
named here (Coding Standards §2.7) rather than inlined at each use site.
Values are drawn directly from the architecture documents; this module
introduces no new business thresholds of its own.
"""

from __future__ import annotations

# --- Confidence / probability / strength bounds (Phase 2.5 §5) -------------
MIN_UNIT_INTERVAL: float = 0.0
MAX_UNIT_INTERVAL: float = 1.0

# --- Risk score bounds (Phase 2.1 §3.5, Phase 2.5 §5) -----------------------
MIN_RISK_SCORE: int = 0
MAX_RISK_SCORE: int = 100

# --- Severity band vocabulary (Phase 1 §5.1, fixed six-band scale) --------
SEVERITY_BANDS: tuple[str, ...] = (
    "negligible",
    "low",
    "moderate",
    "high",
    "critical",
    "catastrophic",
)

# --- Priority tiers (Phase 2.4 §5.3) ---------------------------------------
PRIORITY_TIERS: tuple[str, ...] = ("P0", "P1", "P2", "P3", "P4")

# --- Default TTL for a published RiskScore, seconds (Phase 1 §5.1) --------
DEFAULT_RISK_SCORE_TTL_SECONDS: int = 30

# --- Minimum acceptable agent confidence (Phase 1 §1.11) -------------------
PLATFORM_MIN_CONFIDENCE: float = 0.7

# --- End-to-end pipeline budget, milliseconds (Phase 1 §9.1) ---------------
TOTAL_PIPELINE_BUDGET_MS: int = 1500

# --- Correlation strength / evidence-quality bounds (Phase 2.3 §4.3) -------
MIN_CORRELATION_STRENGTH: float = MIN_UNIT_INTERVAL
MAX_CORRELATION_STRENGTH: float = MAX_UNIT_INTERVAL

# --- Compound findings require evidence from at least this many distinct
#     upstream agents (Phase 2.3 §5.5, Phase 2.5 §9). ----------------------
MIN_DISTINCT_AGENTS_FOR_COMPOUND_FINDING: int = 2

# --- UUID string length sanity bound (defensive, not authoritative) -------
UUID_STRING_LENGTH: int = 36
