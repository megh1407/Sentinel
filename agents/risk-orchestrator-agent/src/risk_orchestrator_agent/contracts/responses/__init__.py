"""Wire-format response/outbound-event contracts.

Empty in this phase by design — see `contracts/requests/__init__.py`'s
docstring. This phase's outbound shapes are represented purely in
`domain/events` (`RiskAssessmentCreated`, `SiteStateChanged`, etc.);
their DTO/wire mapping is a later phase's concern (FRS §6).
"""
