"""Runs notebooks/playtest.ipynb for real and asserts every cell executes cleanly.

A real ipykernel subprocess, a real `uv run story-simulator-mcp` subprocess
(spawned exactly the way the notebook's own `connect()` spawns it), and a
real db-backed world -- not the in-process `_make_ctx()` stand-in
`test_mcp_server.py`/`test_event_loop.py` use. That in-process style can
never catch a bug in how the notebook spawns *its own* subprocess (e.g. the
env-var-not-inherited bug `connect()`'s `env=os.environ.copy()` fixes --
`StdioServerParameters` otherwise hands the child only a hardcoded safe env
subset, silently dropping `STORY_SIM_DATABASE_DSN`), since it never spawns
one at all.
"""

from pathlib import Path

import nbformat
import pytest
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_PATH = REPO_ROOT / "notebooks" / "playtest.ipynb"

pytestmark = pytest.mark.slow


def test_playtest_notebook_runs_without_error():
    nb = nbformat.read(NOTEBOOK_PATH, as_version=4)
    client = NotebookClient(
        nb,
        timeout=120,
        kernel_name="python3",
        # Sets the kernel's own cwd to the repo root -- REPO_ROOT = Path.cwd()
        # in the notebook's connect() cell relies on this to resolve
        # data/playtest_scenario and spawn `uv run story-simulator-mcp`
        # from the right place, the same way the notebook's own markdown
        # tells a human running it interactively to do.
        resources={"metadata": {"path": str(REPO_ROOT)}},
    )
    try:
        client.execute()
    except CellExecutionError as exc:
        pytest.fail(f"playtest.ipynb raised during execution:\n{exc}")
