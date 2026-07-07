import argparse

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from story_simulator.cli import WORLDS
from story_simulator.interpreter import Interpreter

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


class InputRequest(BaseModel):
    text: str


def get_positions(interpreter: Interpreter) -> list[dict]:
    """Return {alias, x, y} for every entity with a position component."""
    architect = getattr(interpreter.world, "architect", None)
    if architect is None:
        return []
    try:
        df = architect.view("position").execute()
    except KeyError:
        return []
    return [
        {
            "alias": row["entity_id.alias"],
            "x": float(row["position.x"]),
            "y": float(row["position.y"]),
        }
        for _, row in df.iterrows()
    ]


def create_app(interpreter: Interpreter) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/positions")
    def read_positions():
        return {"positions": get_positions(interpreter)}

    @app.post("/input")
    def post_input(body: InputRequest):
        response = interpreter.input(body.text)
        return {
            "response": response,
            "stopped": interpreter.stopped,
            "positions": get_positions(interpreter),
        }

    return app


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", choices=WORLDS, default="ensemble")
    parser.add_argument(
        "--save-dir", default=None, help="Directory for the ensemble world's save data."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser.parse_args(argv)


def main(argv=None):
    load_dotenv()
    args = parse_args(argv)
    world = WORLDS[args.world](args)
    interpreter = Interpreter(world=world)
    app = create_app(interpreter)

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
