BANNER = "story-simulator REPL. Type /quit to exit."


def main():
    print(BANNER)
    while True:
        try:
            text = input("> ")
        except EOFError:
            break
        if text.strip() == "/quit":
            break


if __name__ == "__main__":
    main()
