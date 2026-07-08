from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

DEFAULT_RENDER_PATH = Path("render.svg")


def render_positions(architect, path: Path = DEFAULT_RENDER_PATH) -> None:
    """Save an SVG scatter plot of every entity with a position, overwriting `path`."""
    has_positions = "position" in architect.registry.component_types
    if has_positions:
        position = architect.view("position")
        df = position.execute()

    fig, ax = plt.subplots()
    if has_positions and not df.empty:
        ax.scatter(df["position.x"], df["position.y"])
        for _, row in df.iterrows():
            ax.annotate(
                row["entity_id.alias"],
                (row["position.x"], row["position.y"]),
                xytext=(5, 5),
                textcoords="offset points",
            )
    ax.set_aspect("equal", adjustable="datalim")
    fig.savefig(path)
    plt.close(fig)
