from story_simulator.cli import main, BANNER


def test_repl_starts_and_exits(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "/quit")

    main()

    output = capsys.readouterr().out
    assert BANNER in output


def test_non_command_text_gets_response(monkeypatch, capsys):
    inputs = iter(["hello there", "/quit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    main()

    output = capsys.readouterr().out
    assert len(output) > 0
