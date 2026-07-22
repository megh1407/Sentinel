"""
harness_config.py

Central configuration for tools/integration_testing/. Named harness_config.py
rather than config.py on purpose: both agents/environmental-intelligence-agent
and agents/zone_intelligence_agent already have their own top-level `config.py`
module, imported by module name (`import config` / `from config import ...`)
from inside their own business logic. Every worker process in this harness
puts one of those agent directories on sys.path so it can import the agent's
real code unmodified -- if this file were also named config.py and its
directory ended up on sys.path at the same time, Python's module system would
silently resolve `import config` to whichever one sys.path finds first,
which is exactly the kind of accidental cross-wiring a testing harness must
never introduce into the real agent's behavior. Renaming ours is a zero-cost
way to make that class of bug structurally impossible instead of "unlikely."

Nothing here modifies contracts, schemas, topics, the registry, or any
agent's business logic -- it only points at them.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Repository layout -------------------------------------------------
# This file lives at <repo_root>/tools/integration_testing/harness_config.py
HARNESS_DIR = Path(__file__).resolve().parent
REPO_ROOT = HARNESS_DIR.parent.parent
LIBS_DIR = REPO_ROOT / "libs"
ENV_AGENT_DIR = REPO_ROOT / "agents" / "environmental-intelligence-agent"
ENV_AGENT_SRC_DIR = ENV_AGENT_DIR / "src"
ZONE_AGENT_DIR = REPO_ROOT / "agents" / "zone_intelligence_agent"
KAFKA_TOPICS_YAML = REPO_ROOT / "contracts" / "topics" / "kafka_topics.yaml"
DEV_ENV_COMPOSE = REPO_ROOT / "scripts" / "dev-env" / "docker-compose.yml"

for _p in (REPO_ROOT, LIBS_DIR):
    assert _p.exists(), f"expected repo path missing: {_p}"

# --- Runtime state (shared across every worker process) ----------------
STATE_DIR = HARNESS_DIR / ".state"
STATE_DIR.mkdir(exist_ok=True)
TRACE_DB_PATH = str(STATE_DIR / "trace_events.db")
SCENARIO_CONTROL_PATH = STATE_DIR / "scenario_control.json"
REPORT_OUTPUT_PATH = HARNESS_DIR / "integration_report.md"

# --- Kafka ---------------------------------------------------------------
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

# Topics this demo actually exercises, and why. Every name is taken verbatim
# from contracts/topics/kafka_topics.yaml -- never invented locally.
TOPIC_SENSOR_EVENTS = "sentinel.sensor.events.v1"
TOPIC_WORKER_EVENTS = "sentinel.worker.events.v1"
TOPIC_PERMIT_EVENTS = "sentinel.permit.events.v1"
TOPIC_ZONE_STATE = "sentinel.zone.state.v1"
# The two topics below ARE registered in kafka_topics.yaml, but no
# publishable generated model exists for either schema anywhere in the repo
# (verified: `grep -rl "class EnvironmentAnalysis"` / `"class ZoneAnalysis"`
# across the whole tree returns nothing). Kept here, not deleted, so
# kafka_topic_monitor.py can still report their real (empty) state honestly
# instead of pretending they don't exist.
TOPIC_ENVIRONMENT_ANALYSIS = "sentinel.environment.analysis.v1"
TOPIC_ZONE_ANALYSIS = "sentinel.zone.analysis.v1"

DEMO_TOPICS = [
    TOPIC_SENSOR_EVENTS,
    TOPIC_WORKER_EVENTS,
    TOPIC_PERMIT_EVENTS,
    TOPIC_ZONE_STATE,
    TOPIC_ENVIRONMENT_ANALYSIS,
    TOPIC_ZONE_ANALYSIS,
]

# --- Optional: Sentinel_Data_Engine (external, richer fake-data generator) ---
# Not part of the SENTINEL platform proper -- a separate project, vendored here
# at <repo_root>/Sentinel_Data_Engine/ for convenience. Only imported by
# data_engine_adapter.py / fake_data_engine_simulator.py -- nothing else in
# this harness needs it, and the original random-value simulators keep working
# with zero dependency on whether this path even exists. Override via the env
# var if you keep it somewhere else.
DATA_ENGINE_ROOT = Path(os.environ.get("DATA_ENGINE_ROOT", str(REPO_ROOT / "Sentinel_Data_Engine")))

# retry.py's RetryRouter computes destination topics as f"{original_topic}.retry" /
# f"{original_topic}.dlq" dynamically -- there is no registry entry for these anywhere
# (verified: they don't appear in kafka_topics.yaml at all), so nothing in
# contracts/topics/ tells us their partition counts. reset_topics.py creates them
# with 1 partition each -- retry/DLQ traffic is expected to be low-volume relative to
# the source topic, and this is purely a local-dev operational choice, not a contract.
RETRY_DLQ_SOURCE_TOPICS = [TOPIC_SENSOR_EVENTS, TOPIC_WORKER_EVENTS, TOPIC_PERMIT_EVENTS]
DEMO_RETRY_TOPICS = [f"{t}.retry" for t in RETRY_DLQ_SOURCE_TOPICS]
DEMO_DLQ_TOPICS = [f"{t}.dlq" for t in RETRY_DLQ_SOURCE_TOPICS]

CONSUMER_GROUP_ENV_AGENT = "environmental-intelligence-agent"
CONSUMER_GROUP_ZONE_AGENT = "zone-intelligence-agent"

# --- Demo site/zone topology ---------------------------------------------
SITE_ID = "SITE-01"
ZONE_IDS = ["ZONE-A", "ZONE-B", "ZONE-C"]

# --- State backends (zone agent needs Redis; Postgres is optional) --------
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
POSTGRES_DSN = os.environ.get("POSTGRES_DSN")  # unset => zone agent degrades gracefully, same as prod

# --- Simulator pacing ------------------------------------------------------
SENSOR_EVENT_INTERVAL_SECONDS = float(os.environ.get("SENSOR_EVENT_INTERVAL_SECONDS", "1.0"))
WORKER_EVENT_INTERVAL_SECONDS = float(os.environ.get("WORKER_EVENT_INTERVAL_SECONDS", "3.0"))
PERMIT_EVENT_INTERVAL_SECONDS = float(os.environ.get("PERMIT_EVENT_INTERVAL_SECONDS", "7.0"))


def bootstrap_agent_sys_path(*extra_dirs: Path) -> None:
    """Inserts the paths a given agent needs to import its own real code
    unmodified, mirroring the PYTHONPATH recipe already documented in
    agents/zone_intelligence_agent/demo.py's own docstring
    (`PYTHONPATH=../..:../../libs:../../sentinel_contracts:.`). Called once,
    early, by each worker script -- never by this module itself, since not
    every process that imports harness_config needs every agent importable.
    """
    import sys

    for d in (*extra_dirs, REPO_ROOT, LIBS_DIR):
        sd = str(d)
        if sd not in sys.path:
            sys.path.insert(0, sd)


def bootstrap_data_engine_sys_path() -> None:
    """Puts Sentinel_Data_Engine's own root on sys.path so its top-level
    `generators`, `events`, `models`, `config` packages import. Kept
    separate from bootstrap_agent_sys_path() (and never called alongside
    it in the same process) because Sentinel_Data_Engine has its own
    top-level `config` and `events` packages -- names that would otherwise
    collide with the SENTINEL agents' own `config.py` modules if both were
    ever put on sys.path together. fake_data_engine_simulator.py is the
    only process that needs this, and it never imports agent code."""
    import sys

    if not DATA_ENGINE_ROOT.exists():
        raise FileNotFoundError(
            f"DATA_ENGINE_ROOT does not exist: {DATA_ENGINE_ROOT}. "
            f"Set the DATA_ENGINE_ROOT environment variable to wherever you extracted "
            f"Sentinel_Data_Engine, e.g.: export DATA_ENGINE_ROOT=/path/to/Sentinel_Data_Engine"
        )
    sd = str(DATA_ENGINE_ROOT)
    if sd not in sys.path:
        sys.path.insert(0, sd)
