import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "libs"))
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "agents" / "hello_agent"))
sys.path.insert(0, str(REPO_ROOT / "agents" / "response-agent" / "src"))
sys.path.insert(0, str(REPO_ROOT / "agents" / "risk-orchestrator-agent" / "src"))

import pytest
from sentinel_eventbus import reset_all_state


@pytest.fixture(autouse=True)
def _reset_eventbus_state():
    reset_all_state()
    yield
    reset_all_state()


@pytest.fixture
def redis_client():
    import redis
    client = redis.Redis(host="localhost", port=6379, db=0)
    client.ping()  # fail fast if Redis isn't actually up
    yield client
    client.flushdb()


@pytest.fixture
def postgres_session_factory():
    from sentinel_state import build_engine, build_session_factory
    from sentinel_state.postgres_repositories import HelloSeenRepository, Base

    engine = build_engine("postgresql+psycopg2://postgres:localdev@localhost:5432/sentinel")
    session_factory = build_session_factory(engine)
    HelloSeenRepository(session_factory).ensure_schema()
    yield session_factory
    with engine.connect() as conn:
        from sqlalchemy import text
        conn.execute(text("TRUNCATE TABLE hello_agent.hello_seen_events"))
        conn.commit()
