"""Drive the World Soul Managed Agent.

Creates a session against the World Soul agent, streams its narration, and
sends player actions as `user.message` events. See agents/world_soul.agent.yaml
for how to keep this agent's config version-controlled in this repo.
"""

import argparse
import json
import os
import sys

import anthropic

DEFAULT_AGENT_ID = os.environ.get("WORLD_SOUL_AGENT_ID", "agent_01AxMwvbKDkfbVZd73DLNiAy")
DEFAULT_ENVIRONMENT_ID = os.environ.get("WORLD_SOUL_ENVIRONMENT_ID", "env_01Rhk13fhp1wwS3RgiDQcK2g")

# Fields Anthropic assigns server-side; strip these before writing a dumped
# config back into agents/world_soul.agent.yaml, since re-submitting them
# on `ant beta:agents create`/`update` either has no effect or errors.
_READ_ONLY_AGENT_FIELDS = ("id", "version", "created_at", "updated_at", "archived_at")


def create_session(client: anthropic.Anthropic, agent_id: str, environment_id: str, title: str | None = None):
    session = client.beta.sessions.create(agent=agent_id, environment_id=environment_id, title=title)
    print(f"Session: {session.id}", file=sys.stderr)
    print(
        f"Trace: https://platform.claude.com/workspaces/default/sessions/{session.id}",
        file=sys.stderr,
    )
    return session


def send_player_action(client: anthropic.Anthropic, session_id: str, text: str) -> None:
    client.beta.sessions.events.send(
        session_id=session_id,
        events=[{"type": "user.message", "content": [{"type": "text", "text": text}]}],
    )


def play_turn(client: anthropic.Anthropic, session_id: str, action_text: str) -> None:
    """Send one player action and print the agent's narration until it's idle."""
    # Stream-first: open the stream before sending so no events are missed.
    with client.beta.sessions.events.stream(session_id=session_id) as stream:
        send_player_action(client, session_id, action_text)
        for event in stream:
            if event.type == "agent.message":
                for block in event.content:
                    if block.type == "text":
                        print(block.text, end="", flush=True)
            elif event.type == "session.status_idle":
                print()
                if event.stop_reason.type != "requires_action":
                    return
            elif event.type == "session.status_terminated":
                print("\n[session terminated]", file=sys.stderr)
                raise SystemExit(1)


def run_interactive(client: anthropic.Anthropic, agent_id: str, environment_id: str) -> None:
    session = create_session(client, agent_id, environment_id, title="World Soul session")
    print("Describe your action at each prompt (Ctrl-D to quit).\n")
    try:
        while True:
            action = input("> ")
            if action.strip():
                play_turn(client, session.id, action)
    except EOFError:
        print()


def dump_agent_config(client: anthropic.Anthropic, agent_id: str) -> None:
    """Print the agent's current config as JSON (valid YAML) for version control.

    Usage: world-soul --dump-config > agents/world_soul.agent.yaml
    """
    agent = client.beta.agents.retrieve(agent_id)
    config = agent.to_dict()
    for field in _READ_ONLY_AGENT_FIELDS:
        config.pop(field, None)
    print(json.dumps(config, indent=2))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Play through a World Soul session.")
    parser.add_argument("--agent-id", default=DEFAULT_AGENT_ID)
    parser.add_argument("--environment-id", default=DEFAULT_ENVIRONMENT_ID)
    parser.add_argument("action", nargs="?", help="Send a single action instead of playing interactively")
    parser.add_argument(
        "--dump-config",
        action="store_true",
        help="Fetch the agent's live config and print it (pipe into agents/world_soul.agent.yaml)",
    )
    args = parser.parse_args(argv)

    try:
        client = anthropic.Anthropic()
        if args.dump_config:
            dump_agent_config(client, args.agent_id)
        elif args.action:
            session = create_session(client, args.agent_id, args.environment_id, title="World Soul session")
            play_turn(client, session.id, args.action)
        else:
            run_interactive(client, args.agent_id, args.environment_id)
    except (anthropic.AuthenticationError, TypeError) as e:
        if isinstance(e, TypeError) and "authentication" not in str(e).lower():
            raise
        sys.exit(
            "Authentication failed. Set the ANTHROPIC_API_KEY environment variable "
            "(or run `ant auth login`) and try again."
        )
    except anthropic.APIError as e:
        sys.exit(f"Claude API error: {e}")


if __name__ == "__main__":
    main()
