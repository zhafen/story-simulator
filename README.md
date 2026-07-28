# story-simulator

## Running the REPL

```
./run.sh
```

Type `/help` to list available commands, or `/quit` to exit. `run.sh` forwards any arguments to `story_simulator.cli`, e.g.
`./run.sh --world mirror`.

Defaults to the `ensemble` world, saving to a throwaway sandbox at `./data/sandbox` seeded from
the plain default world at `./data/default` (override with `--world`/`--save-dir`, or pass
`--living` to edit the tracked, ever-growing living world at `./data/living_world` directly — it
has its own teleport-and-advance-time door mechanic, see `data/living_world/setting.yaml`).
For the `ensemble` world, an SVG scatter plot of every entity with a position is (re)written to
`<save-dir>/render.svg` after each turn (override with `--render-path`).

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the turn pipeline, how each agent
(Resolver, Archivist, NPC, and the Terrain/Physics specialists) is configured and called, and
how the Resolver delegates to Terrain/Physics on demand.
