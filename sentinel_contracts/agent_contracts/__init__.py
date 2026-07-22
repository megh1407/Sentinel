"""
sentinel_contracts.agent_contracts

New subpackage (this task is the first thing to populate it) mirroring the
sibling `common`/`events` subpackages, for generated models whose source
.avsc lives under contracts/agent-contracts/ rather than contracts/events/.
tools/codegen/avro_to_pydantic.py already targets this layout when its
OUT_ROOT is corrected (see that file's DEPRECATED.md-documented drift --
its default OUT_ROOT still points at the removed libs/sentinel_contracts/
duplicate; the OUT_ROOT drift itself is still not fixed here, so this file
remains hand-mirrored from the .avsc rather than tool-generated -- a
genuine follow-up, not done here to keep this change scoped to the two
models this task needed.

PermitAnalysisV1 was added first (Permit Agent task). EnvironmentAnalysisV1
was added by this task, mechanically mirrored field-for-field from
contracts/agent-contracts/v1/EnvironmentAnalysis.avsc using the identical
pattern PermitAnalysisV1 established -- no field invented, none changed.
ZoneAnalysis and WorkerAnalysis remain unwritten; see zone_intelligence_agent
and worker_safety_agent's own main.py/README notes for their status.
"""
from .permit_analysis_v1 import PermitAnalysisV1
from .environment_analysis_v1 import EnvironmentAnalysisV1
from .worker_analysis_v1 import WorkerAnalysisV1
