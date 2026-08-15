"""safety_copilot.py -- LLM Safety Copilot.

STRICT BOUNDARY (master prompt's non-negotiable rule): this module explains
verified data. It never calculates risk, severity, or emergency status --
those stay owned entirely by the Risk Orchestrator and Response Agent. The
LLM only ever sees the already-finalized SafetyExplanation + assessment; it
cannot see raw events, and has no path back into the risk pipeline.

Uses Google's Gemini API (free tier: aistudio.google.com, no credit card).
Set GEMINI_API_KEY to enable it. Without a key, or if the request fails,
times out, or returns something unusable, every function here falls back
to the deterministic explanation from safety_explanation.py -- the safety
dashboard must never go blank or wait on the LLM (Phase 13/14 of the spec).
"""
from __future__ import annotations

import json
import os

import requests

from safety_explanation import SafetyExplanation

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
REQUEST_TIMEOUT_SECONDS = 8

SYSTEM_INSTRUCTIONS = """You are SENTINEL Safety Copilot.

Your role is to explain verified industrial safety assessments clearly.
You are not the risk calculation system. You are not authorized to change:
risk score, severity, decision category, emergency status, recommended
action, or escalation requirement -- those are fixed inputs, already
decided by the Risk Orchestrator and Response Agent.

Use only the supplied verified assessment. Do not invent hazards, sensor
values, workers, permit conflicts, affected zones, propagation paths, or
any other safety evidence not present in the supplied context.

If information is missing, say: "Insufficient information is available
for this part of the assessment." Do not claim a condition is safe when
data is missing. Explain in concise, operational language."""


def llm_available() -> bool:
    return bool(GEMINI_API_KEY) and GEMINI_API_KEY != "PLACEHOLDER_ADD_YOUR_KEY"


def _build_context(explanation: SafetyExplanation) -> dict:
    """The LLM input contract from the master prompt (Phase 8), built only
    from already-verified SafetyExplanation fields -- no raw internal code,
    no unverified data."""
    return {
        "assessment_id": explanation.assessment_id,
        "zone_id": explanation.zone_id,
        "severity": explanation.severity.upper(),
        "decision": explanation.decision_category.upper(),
        "global_risk": explanation.global_score,
        "primary_hazard": explanation.primary_hazard,
        "affected_zones": explanation.affected_zones,
        "verified_risk_factors": [
            {"factor": f, "source": c.agent, "impact": c.impact}
            for c in explanation.agent_contributions
            for f in c.findings
        ],
        "verified_propagation": explanation.propagation_impact,
        "recommended_action": explanation.immediate_action,
        "analysis_completeness": explanation.analysis_completeness,
        "missing_domains": explanation.missing_domains,
    }


def _call_gemini(prompt: str) -> str | None:
    """Returns the model's text, or None on any failure -- callers must
    treat None as 'fall back to deterministic', never as an error to
    surface to the safety dashboard. Failures ARE logged though, so they're
    diagnosable instead of silently invisible."""
    import logging
    log = logging.getLogger(__name__)

    if not llm_available():
        log.info("gemini_skipped_no_key")
        return None
    try:
        resp = requests.post(
            GEMINI_URL,
            params={"key": GEMINI_API_KEY},
            json={
                "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTIONS}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400},
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if not resp.ok:
            log.warning("gemini_http_error", extra={"status": resp.status_code, "body": resp.text[:500]})
            return None
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:  # noqa: BLE001 -- any failure mode falls back, never raises
        log.warning("gemini_call_failed", extra={"error": str(e)})
        return None


def explain_conversationally(explanation: SafetyExplanation) -> dict:
    """Enhanced, natural-language version of the deterministic summary.
    Always returns a usable brief -- deterministic text if the LLM is
    unavailable/fails, so the dashboard is never blocked on this."""
    context = _build_context(explanation)
    prompt = (
        "Here is a verified industrial safety assessment as structured JSON:\n\n"
        f"{json.dumps(context, indent=2)}\n\n"
        "Write a short (3-5 sentence) operational safety brief a plant operator "
        "could read in a few seconds. State what is happening, why, and the "
        "recommended action. Do not restate the raw JSON."
    )
    text = _call_gemini(prompt)
    if text is not None:
        return {"text": text, "source": "llm", "model": GEMINI_MODEL}
    return {"text": explanation.summary + " " + explanation.why_this_matters, "source": "deterministic", "model": None}


def ask(explanation: SafetyExplanation, question: str) -> dict:
    """Answers a free-text question about the assessment, constrained to
    verified context only. Falls back to a deterministic canned answer
    for the six required questions (Phase 9) if the LLM is unavailable."""
    context = _build_context(explanation)
    prompt = (
        "Here is a verified industrial safety assessment as structured JSON:\n\n"
        f"{json.dumps(context, indent=2)}\n\n"
        f'The operator asks: "{question}"\n\n'
        "Answer using only the verified context above. If the question asks "
        "about something not present in the context, say so explicitly rather "
        "than guessing."
    )
    text = _call_gemini(prompt)
    if text is not None:
        return {"text": text, "source": "llm", "model": GEMINI_MODEL}
    return {"text": _deterministic_answer(explanation, question), "source": "deterministic", "model": None}


def _deterministic_answer(explanation: SafetyExplanation, question: str) -> str:
    """No-LLM fallback for the six required Copilot questions (Phase 9).
    Simple keyword routing -- not a language model, just verified-field
    lookup, so this always works even with GEMINI_API_KEY unset."""
    q = question.lower()

    if "why" in q and ("high" in q or "risk" in q) and "emergency" not in q:
        return explanation.why_this_matters

    if "emergency" in q:
        if explanation.decision_category == "emergency":
            return (
                f"This is classified as an emergency because the verified assessment shows "
                f"{explanation.severity} risk (score {explanation.global_score:.1f}) "
                f"with escalation required."
            )
        return f"This is not currently classified as an emergency -- decision category is {explanation.decision_category}."

    if "agent" in q and "contribut" in q:
        if not explanation.agent_contributions:
            return "No agent contributions are recorded for this assessment."
        parts = [f"{c.agent} ({c.impact.lower()})" for c in explanation.agent_contributions]
        return "The following contributed to this assessment: " + ", ".join(parts) + "."

    if "affect" in q or "propagat" in q or "zone-b" in q or "spread" in q:
        if explanation.propagation_impact:
            return " ".join(explanation.propagation_impact)
        return "No propagation to other zones is indicated in the verified assessment."

    if "what should" in q or "now" in q or "do" in q:
        return explanation.immediate_action or "No specific action has been recommended by the Response Agent yet."

    if "missing" in q or "incomplete" in q:
        return explanation.analysis_limitations or "The assessment is complete -- no missing domains reported."

    return (
        "Insufficient information is available for this part of the assessment, "
        "or this question isn't covered by the deterministic fallback (the LLM "
        "is currently unavailable -- set GEMINI_API_KEY for open-ended questions)."
    )
