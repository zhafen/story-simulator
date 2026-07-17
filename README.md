# story-simulator

## Running the REPL

```
./run.sh
```

Type `/quit` to exit. `run.sh` forwards any arguments to `story_simulator.cli`, e.g.
`./run.sh --world mirror`.

Defaults to the `ensemble` world, saving to a throwaway sandbox at `./data/sandbox` seeded from
the tracked living world (override with `--world`/`--save-dir`, or pass `--living` to edit the
tracked living world at `./data/default` directly).
For the `ensemble` world, an SVG scatter plot of every entity with a position is (re)written to
`<save-dir>/render.svg` after each turn (override with `--render-path`).
