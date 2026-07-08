import argparse
from pathlib import Path

from dotenv import load_dotenv

from story_simulator.config import TEST_AGENT_ID
from story_simulator.interpreter import Interpreter
from story_simulator.world import AgentWorld, EnsembleWorld, MirrorWorld, TEST_AGENT_CONFIG_PATH

BANNER = "story-simulator REPL. Type /quit to exit."

WORLDS = {
    "agent": lambda args: AgentWorld(),
    "agent-test": lambda args: AgentWorld(agent_id=TEST_AGENT_ID, config_path=TEST_AGENT_CONFIG_PATH),
    "mirror": lambda args: MirrorWorld(),
    "ensemble": lambda args: EnsembleWorld(
        save_dir=args.save_dir,
        render_path=Path(args.render_path) if args.render_path else Path(args.save_dir) / "render.svg",
    ),
}


DEFAULT_SAVE_DIR = "./data/default"


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", choices=WORLDS, default="ensemble")
    parser.add_argument(
        "--save-dir",
        default=DEFAULT_SAVE_DIR,
        help="Directory for the ensemble world's save data.",
    )
    parser.add_argument(
        "--render-path",
        default=None,
        help="Where to overwrite an SVG render of entity positions each turn "
        "(default: render.svg next to --save-dir).",
    )
    return parser.parse_args(argv)


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
