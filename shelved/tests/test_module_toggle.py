"""Test for the character/base module toggle (story_simulator.config.enabled_modules).

Shelved alongside the toggle itself (see docs/architecture.md) -- with the
character branch removed from _run_event_loop, advance_simulation always
takes the base path now, so this test's premise (default config picks the
character branch) no longer holds. Outside `testpaths` (tests/), so not
collected by pytest; kept as reference for pulling the toggle back in.
"""

import asyncio
from unittest.mock import MagicMock

from story_simulator.mcp_server import advance_simulation, start_world, update_registry


def _make_ctx():
    ctx = MagicMock()
    ctx.request_context.session = MagicMock()
    return ctx


def test_default_config_runs_the_character_branch_instead(tmp_path):
    """Sanity check on the module toggle itself: with STORY_SIM_MODULES
    unset (the default -- see enabled_modules), advance_simulation takes
    the character branch, not the base one, even for a world with no
    characters -- so it reports nothing scheduled rather than picking up a
    bare next_due row the way the base branch would."""
    ctx = _make_ctx()
    scenario_dir = tmp_path / "empty_scenario"
    scenario_dir.mkdir()
    start_world(str(tmp_path / "save"), ctx, scenario_dir=str(scenario_dir))
    update_registry("gizmo:\n    - next_due:\n        value: 0\n", ctx=ctx)

    result = asyncio.run(advance_simulation(ctx))
    assert result == {"status": "done", "narration": "Nothing scheduled."}
