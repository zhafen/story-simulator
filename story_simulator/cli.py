from story_simulator.world import MirrorWorld

BANNER = "story-simulator REPL. Type /quit to exit."


def main(world=None):
    if world is None:
        world = MirrorWorld()
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
