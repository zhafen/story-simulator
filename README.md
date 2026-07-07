# story-simulator

## Running the REPL

```
./run.sh
```

Type `/quit` to exit.

For the `ensemble` world, an SVG scatter plot of every entity with a position is (re)written to
`render.svg` after each turn (next to `--save-dir` if given, else in the current directory):

```
uv run python -m story_simulator.cli --world ensemble --save-dir /path/to/save-dir
```

Override the render location with `--render-path`.
