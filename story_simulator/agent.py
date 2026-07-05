"""Simple CLI for sending a prompt to a Claude agent and printing its response."""

import argparse
import sys

import anthropic

DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_MAX_TOKENS = 4096


def ask_agent(prompt: str, model: str = DEFAULT_MODEL, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    """Send `prompt` to a Claude agent and return its text response."""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Send a prompt to a Claude agent and print its response."
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="The prompt to send. If omitted, the prompt is read from stdin.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model to use (default: {DEFAULT_MODEL})")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"Maximum tokens to generate (default: {DEFAULT_MAX_TOKENS})",
    )
    args = parser.parse_args(argv)

    prompt = args.prompt if args.prompt is not None else sys.stdin.read()
    if not prompt.strip():
        parser.error("no prompt provided (pass it as an argument or via stdin)")

    try:
        print(ask_agent(prompt, model=args.model, max_tokens=args.max_tokens))
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
