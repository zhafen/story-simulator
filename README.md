# story-simulator

## Running the REPL

```
./run.sh
```

Type `/quit` to exit.

## Running the local server + UI

The UI talks to a local FastAPI server that wraps a `World`. Start it with:

```
uv run python -m story_simulator.server --world ensemble --save-dir /path/to/save-dir
```

`--world` accepts `agent`, `agent-test`, `mirror`, or `ensemble` (default `ensemble`); `--save-dir`
is only used by the `ensemble` world. It serves on `http://127.0.0.1:8000` by default
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
