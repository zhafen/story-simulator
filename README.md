# story-simulator

## Running the REPL

```
./run.sh
```

Type `/help` to list available commands, or `/quit` to exit. `run.sh` forwards any arguments to `story_simulator.cli`, e.g.
`./run.sh --world mirror`.

Defaults to the `ensemble` world, saving to `./data/default` (override with `--world`/`--save-dir`).
For the `ensemble` world, an SVG scatter plot of every entity with a position is (re)written to
`<save-dir>/render.svg` after each turn (override with `--render-path`).
