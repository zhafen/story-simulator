import argparse
from pathlib import Path

from dotenv import load_dotenv

from story_simulator.config import LIVING_WORLD_DIR, TEST_AGENT_ID
from story_simulator.interpreter import Interpreter
from story_simulator.world import AgentWorld, EnsembleWorld, MirrorWorld, TEST_RESOLVER_CONFIG_PATH

BANNER = "story-simulator REPL. Type /quit to exit."

WORLDS = {
    "agent": lambda args: AgentWorld(),
    "agent-test": lambda args: AgentWorld(agent_id=TEST_AGENT_ID, config_path=TEST_RESOLVER_CONFIG_PATH),
    "mirror": lambda args: MirrorWorld(),
    "ensemble": lambda args: EnsembleWorld(
        save_dir=args.save_dir,
        render_path=Path(args.render_path) if args.render_path else Path(args.save_dir) / "render.svg",
    ),
}


DEFAULT_SAVE_DIR = "./data/sandbox"


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", choices=WORLDS, default="ensemble")
    save_dir_group = parser.add_mutually_exclusive_group()
    save_dir_group.add_argument(
        "--save-dir",
        default=None,
        help="Directory for the ensemble world's save data (default: a "
        f"throwaway sandbox at {DEFAULT_SAVE_DIR}, seeded from the living world).",
    )
    save_dir_group.add_argument(
        "--living",
        dest="save_dir",
        action="store_const",
        const=str(LIVING_WORLD_DIR),
        help="Keep editing the tracked, ever-growing living world at "
        f"{LIVING_WORLD_DIR} instead of a throwaway sandbox copy.",
    )
    parser.add_argument(
        "--render-path",
        default=None,
        help="Where to overwrite an SVG render of entity positions each turn "
        "(default: render.svg next to --save-dir).",
    )
    args = parser.parse_args(argv)
    if args.save_dir is None:
        args.save_dir = DEFAULT_SAVE_DIR
    return args


def main(world=None, argv=None):
    load_dotenv()
    if world is None:
        args = parse_args(argv)
        world = WORLDS[args.world](args)

    interpreter = Interpreter(world=world)
    print(BANNER)
    while True:
        try:
            text = input("> ")
        except EOFError:
            break
        response = interpreter.input(text)
        if interpreter.stopped:
            break
        if response is not None:
            print(response)


if __name__ == "__main__":
    main()
