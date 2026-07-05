import json
from unittest.mock import MagicMock

from story_simulator.world_soul import dump_agent_config, play_turn


class _FakeStream:
    """Minimal stand-in for the SDK's `with client.beta.sessions.events.stream(...) as stream:`."""

    def __init__(self, events):
        self._events = events

    def __enter__(self):
        return iter(self._events)

    def __exit__(self, *exc_info):
        return False


def _text_event(event_type, text):
    return MagicMock(type=event_type, content=[MagicMock(type="text", text=text)])


def _idle_event(stop_reason_type):
    return MagicMock(type="session.status_idle", stop_reason=MagicMock(type=stop_reason_type))


def test_play_turn_streams_narration_and_sends_action(capsys):
    events = [
        _text_event("agent.message", "You open your eyes."),
        _idle_event("end_turn"),
    ]
    client = MagicMock()
    client.beta.sessions.events.stream.return_value = _FakeStream(events)

    play_turn(client, "sesn_123", "open my eyes")

    client.beta.sessions.events.send.assert_called_once_with(
        session_id="sesn_123",
        events=[{"type": "user.message", "content": [{"type": "text", "text": "open my eyes"}]}],
    )
    assert "You open your eyes." in capsys.readouterr().out


def test_play_turn_keeps_reading_when_requires_action(capsys):
    events = [
        _text_event("agent.message", "A tool runs..."),
        _idle_event("requires_action"),
        _text_event("agent.message", " and finishes."),
        _idle_event("end_turn"),
    ]
    client = MagicMock()
    client.beta.sessions.events.stream.return_value = _FakeStream(events)

    play_turn(client, "sesn_123", "do a thing")

    out = capsys.readouterr().out
    assert "A tool runs..." in out
    assert "and finishes." in out


def test_dump_agent_config_strips_read_only_fields(capsys):
    client = MagicMock()
    client.beta.agents.retrieve.return_value.to_dict.return_value = {
        "id": "agent_123",
        "version": 4,
        "created_at": "2026-01-01T00:00:00Z",
        "name": "World Soul",
        "model": "claude-opus-4-8",
    }

    dump_agent_config(client, "agent_123")

    printed = json.loads(capsys.readouterr().out)
    assert printed == {"name": "World Soul", "model": "claude-opus-4-8"}
