import pytest

from story_simulator.cli import main, parse_args, BANNER
from story_simulator.config import LIVING_WORLD_DIR
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


def test_world_defaults_to_ensemble():
    assert parse_args([]).world == "ensemble"


def test_world_flag_selects_mirror():
    assert parse_args(["--world", "mirror"]).world == "mirror"


def test_world_flag_selects_agent_test():
    assert parse_args(["--world", "agent-test"]).world == "agent-test"


def test_save_dir_flag_defaults_to_sandbox():
    assert parse_args([]).save_dir == "./data/sandbox"


def test_save_dir_flag_is_parsed():
    args = parse_args(["--world", "ensemble", "--save-dir", "/tmp/some-save"])
    assert args.save_dir == "/tmp/some-save"


def test_living_flag_selects_living_world_dir():
    args = parse_args(["--living"])
    assert args.save_dir == str(LIVING_WORLD_DIR)


def test_living_and_save_dir_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        parse_args(["--living", "--save-dir", "/tmp/some-save"])
