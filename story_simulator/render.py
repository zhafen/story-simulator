from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from story_simulator.positions import get_positions

DEFAULT_RENDER_PATH = Path("render.svg")


def render_positions(architect, path: Path = DEFAULT_RENDER_PATH) -> None:
    """Save an SVG scatter plot of every entity with a position, overwriting `path`."""
    positions = get_positions(architect)

    fig, ax = plt.subplots()
    if positions:
        xs = [p["x"] for p in positions]
        ys = [p["y"] for p in positions]
        ax.scatter(xs, ys)
        for p in positions:
            ax.annotate(p["alias"], (p["x"], p["y"]), xytext=(5, 5), textcoords="offset points")
    ax.set_aspect("equal", adjustable="datalim")
    fig.savefig(path)
    plt.close(fig)
