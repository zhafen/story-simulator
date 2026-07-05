from story_simulator.cli import main, parse_args, BANNER
from story_simulator.world import MirrorWorld


def test_repl_starts_and_exits(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "/quit")

    main(world=MirrorWorld())

    output = capsys.readouterr().out
    assert BANNER in output


def test_non_command_text_gets_response(monkeypatch, capsys):
    inputs = iter(["hello there", "/quit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    main(world=MirrorWorld())

    output = capsys.readouterr().out
    # Check that there's more than just the banner
    assert len(output) > len(BANNER) + 1


def test_world_defaults_to_agent():
    assert parse_args([]).world == "agent"


def test_world_flag_selects_mirror():
    assert parse_args(["--world", "mirror"]).world == "mirror"


def test_world_flag_selects_agent_test():
    assert parse_args(["--world", "agent-test"]).world == "agent-test"
