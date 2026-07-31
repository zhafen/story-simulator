"""Live end-to-end tests that drive story-simulator-mcp through a real MCP client.

Post-MCP-rebuild replacement for the old test_startup_one_loop_save (removed
in acb2956 along with EnsembleWorld/Interpreter): there is no in-process
narrator left to call directly, so these spawn `claude -p` as a real
subprocess against this repo's .mcp.json, exactly the way the README's
quick-start describes a client connecting. Deliberately not built on
story_simulator.agents.run_tool_loop -- reusing this project's own
narrowly-scoped agent-loop code (built for advance_npc_turn's decide/narrate
step, not general narration) as the test driver would mean the "client"
checking the server was written by the same hand, with the same
assumptions, as the server itself.
"""

import json
import shutil
import subprocess
from pathlib import Path

import psycopg
import pytest

from iacs.registrar import Registrar
from story_simulator.config import registry_schema_name, registry_url, resolve_database_dsn

REPO_ROOT = Path(__file__).parent.parent

# Cheapest available model. Kept deliberately weak rather than swapped for a
# stronger one: story-simulator's tools need to hold up under a bad model's
# mistakes, not just a good one's, so that's the model these tests exercise.
LOW_QUALITY_MODEL = "claude-haiku-4-5-20251001"


def _run_headless_turn(prompt: str, *, model: str = LOW_QUALITY_MODEL, timeout: int = 180) -> str:
    """Run one single-turn headless `claude -p` session against this repo's MCP servers.

    One prompt in, one narrated reply out -- whatever tool calls
    story-simulator-mcp needs to answer it happen inside that single turn,
    same as a real player's first message would trigger.
    """
    if shutil.which("claude") is None:
        pytest.skip("claude CLI not on PATH")

    result = subprocess.run(
        [
            "claude",
            "-p",
            prompt,
            "--mcp-config",
            ".mcp.json",
            "--strict-mcp-config",
            "--allowedTools",
            "mcp__story-simulator__*",
            "mcp__iacs__*",
            "--model",
            model,
            "--output-format",
            "json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    assert result.returncode == 0, f"claude exited {result.returncode}: {result.stderr}"
    payload = json.loads(result.stdout)
    assert not payload["is_error"], payload
    return payload["result"]


@pytest.mark.live
def test_startup_one_loop_save(tmp_path):
    """Starts a default-world save via story-simulator-mcp and looks around, in one turn.

    This should trigger at least:
    1. `start_world` seeding the save from the default world.
    2. The connected agent narrating back mention of the door and the empty expanse.
    """
    save_dir = tmp_path / "test_save"

    narration = _run_headless_turn(
        f"Use start_world with save_dir={save_dir} to open a story-simulator world. "
        "Then, as the player: I look around. What do I see?"
    )

    # The player should see mention of the empty expanse and the door.
    assert "door" in narration.lower()
    assert "empty" in narration.lower()

    # The claude -p subprocess (and the story-simulator-mcp server it spawned
    # as its own child) has exited by now, releasing its connection --
    # reconnect to the same schema to check what actually got recorded, the
    # same way the pre-MCP test read `w.registry` in-process. The registry
    # database lets any process open its own connection to shared, live
    # state, so this would work even before the subprocess exits.
    #
    # A weak model can narrate a plausible-sounding scene without ever
    # calling start_world -- confirm the schema actually got created before
    # asserting on its effects, so that failure mode reads as a clear
    # message rather than silently reading whichever schema the current
    # Postgres backend falls through to when the named one doesn't exist
    # (see config.registry_url's docstring).
    schema = registry_schema_name(save_dir)
    with psycopg.connect(resolve_database_dsn()) as con:
        schema_exists = (
            con.execute(
                "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s",
                (schema,),
            ).fetchone()
            is not None
        )
    assert schema_exists, (
        f"No registry schema was ever created for {save_dir} -- start_world "
        f"was not actually called despite this narration: {narration!r}"
    )
    r = Registrar.load(registry_url(save_dir))

    # At least two positions (player, door; the default world's expanse too)
    assert r.get("position").count().execute() >= 2
    # One origin
    assert r.get("origin").count().execute() == 1
    # One character, of interaction type player
    assert (characters := r.get("character")).count().execute() == 1
    assert (
        characters.filter(characters.interaction_type == "player").count().execute()
        == 1
    )
    # At least one object, which is a door
    assert (objects := r.get("object")).count().execute() >= 1
    assert objects.filter(objects.type.contains("door")).count().execute() == 1
    # At least two of the default world's starting entities carry their own
    # description. (The old test checked an `appearance` component type;
    # that's since been retired in favor of iacs's own builtin `description`
    # -- which every declared component/field also uses for its own
    # docstring, so this filters down to the starting aliases rather than
    # counting the several dozen unrelated schema-doc rows that come with
    # any manifest.)
    descriptions = r.view("description").execute()
    starting_aliases = {"player", "door", "expanse"}
    assert descriptions["entity_id.alias"].isin(starting_aliases).sum() >= 2
