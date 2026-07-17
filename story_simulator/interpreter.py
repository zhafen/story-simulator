from story_simulator.world import EnsembleWorld, World

COMMANDS = {
    "/help": "Show this list of available commands.",
    "/quit": "Exit the REPL.",
}


class Interpreter:
    """Interprets a line of input against a World, independent of any UI."""

    def __init__(self, world: World | None = None):
        self.world = world if world is not None else EnsembleWorld()
        self.stopped = False

    def input(self, text: str) -> str | None:
        """Process one line of input.

        Returns the response text to display, or None if there's nothing
        to display (e.g. the input was a command).
        """
        stripped = text.strip()
        if stripped == "/quit":
            self.stopped = True
            return None
        if stripped == "/help":
            return self._help_text()
        if text.startswith("/"):
            return None
        return self.world.respond(text)

    @staticmethod
    def _help_text() -> str:
        return "Available commands:\n" + "\n".join(
            f"  {name} - {description}" for name, description in COMMANDS.items()
        )
