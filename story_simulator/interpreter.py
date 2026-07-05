from story_simulator.world import MirrorWorld, World


class Interpreter:
    """Interprets a line of input against a World, independent of any UI."""

    def __init__(self, world: World | None = None):
        self.world = world if world is not None else MirrorWorld()
        self.stopped = False

    def input(self, text: str) -> str | None:
        """Process one line of input.

        Returns the response text to display, or None if there's nothing
        to display (e.g. the input was a command).
        """
        if self._is_quit(text):
            self.stopped = True
            return None
        if text.startswith("/"):
            return None
        return self.world.respond(text)

    @staticmethod
    def _is_quit(text: str) -> bool:
        return text.strip() == "/quit"
