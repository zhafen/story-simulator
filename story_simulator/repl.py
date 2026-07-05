from story_simulator.world import World


def is_quit(text: str) -> bool:
    return text.strip() == "/quit"


def handle_input(world: World, text: str) -> str | None:
    """Process one line of input against `world`.

    Returns the response text to display, or None if there's nothing to
    display (e.g. the input was a command other than /quit).
    """
    if text.startswith("/"):
        return None
    return world.respond(text)
