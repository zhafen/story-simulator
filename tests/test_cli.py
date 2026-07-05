from story_simulator.cli import main, BANNER


def test_repl_starts_and_exits(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "/quit")

    main()

    output = capsys.readouterr().out
    assert BANNER in output
