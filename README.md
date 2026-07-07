# story-simulator

## Running the REPL

```
./run.sh
```

Type `/quit` to exit. `run.sh` forwards any arguments to `story_simulator.cli`, e.g.
`./run.sh --world mirror`.

Defaults to the `ensemble` world, saving to `./data/default` (override with `--world`/`--save-dir`).
For the `ensemble` world, an SVG scatter plot of every entity with a position is (re)written to
`<save-dir>/render.svg` after each turn (override with `--render-path`).

## Running the local server + UI

The UI talks to a local FastAPI server that wraps a `World`. Start it with:

```
uv run python -m story_simulator.server
```

Same defaults as the REPL (`--world ensemble`, `--save-dir ./data/default`); `--world` also
accepts `agent`, `agent-test`, or `mirror`. It serves on `http://127.0.0.1:8000` by default
(override with `--host`/`--port`).

Then, in a separate terminal, start the Vite dev server for the UI:

```
cd ui
npm install   # first time only
npm run dev
```

Once it prints `http://localhost:5173`, start Electron in a third terminal to load it:

```
cd ui
npm run electron
```

(You can also just open `http://localhost:5173` in a regular browser instead of Electron, e.g.
for quick visual checks.)
