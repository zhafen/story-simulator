import argparse

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from story_simulator.cli import WORLDS
from story_simulator.interpreter import Interpreter
from story_simulator.positions import get_positions

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


class InputRequest(BaseModel):
    text: str


def _positions_for(interpreter: Interpreter) -> list[dict]:
    return get_positions(getattr(interpreter.world, "architect", None))


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
        return {"positions": _positions_for(interpreter)}

    @app.post("/input")
    def post_input(body: InputRequest):
        response = interpreter.input(body.text)
        return {
            "response": response,
            "stopped": interpreter.stopped,
            "positions": _positions_for(interpreter),
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
