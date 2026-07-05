import argparse

from dotenv import load_dotenv

from story_simulator.config import TEST_AGENT_ID
from story_simulator.world import AgentWorld, MirrorWorld, TEST_AGENT_CONFIG_PATH

BANNER = "story-simulator REPL. Type /quit to exit."

WORLDS = {
    "agent": AgentWorld,
    "agent-test": lambda: AgentWorld(agent_id=TEST_AGENT_ID, config_path=TEST_AGENT_CONFIG_PATH),
    "mirror": MirrorWorld,
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", choices=WORLDS, default="agent")
    return parser.parse_args(argv)


def main(world=None, argv=None):
    load_dotenv()
    if world is None:
        args = parse_args(argv)
        world = WORLDS[args.world]()
    print(BANNER)
    while True:
        try:
            text = input("> ")
        except EOFError:
            break
        if text.strip() == "/quit":
            break
        elif not text.startswith("/"):
            print(world.respond(text))


if __name__ == "__main__":
    main()
