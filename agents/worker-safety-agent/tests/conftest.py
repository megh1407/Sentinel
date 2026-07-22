import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = AGENT_ROOT.parent.parent

sys.path.insert(0, str(REPO_ROOT / "libs"))
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(AGENT_ROOT / "src" / "worker_safety_agent"))

import pytest
from sentinel_eventbus import reset_all_state


@pytest.fixture(autouse=True)
def _reset_eventbus_state():
    reset_all_state()
    yield
    reset_all_state()
