"""EvidenceCollection value object (Phase 2.2 §11.1).

Not an audit convenience — the raw material ExplanationBuilder depends on
in a later phase, and the enforcement point for ContextBuilder's
validation step (Phase 2.2 §11.2): a context containing a populated fact
with no corresponding evidence entry is rejected.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from risk_orchestrator_agent.domain.models.evidence import EvidenceItem


@dataclass(frozen=True, slots=True)
class EvidenceCollection:
    items: tuple[EvidenceItem, ...] = field(default_factory=tuple)

    def get(self, evidence_id: str) -> EvidenceItem | None:
        for item in self.items:
            if item.evidence_id == evidence_id:
                return item
        return None

    def merged_with(self, other: "EvidenceCollection") -> "EvidenceCollection":
        """Structural, additive merge — never drops an existing item."""
        seen = {item.evidence_id for item in self.items}
        additional = tuple(i for i in other.items if i.evidence_id not in seen)
        return EvidenceCollection(items=self.items + additional)

    def __len__(self) -> int:
        return len(self.items)
