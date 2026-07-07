def get_positions(architect) -> list[dict]:
    """Return {alias, x, y} for every entity with a position component."""
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


def get_labeled_positions(
    architect, component: str, label_field: str
) -> list[tuple[str, str, tuple[float, float]]]:
    """Return (alias, label, (x, y)) for entities with `component.label_field` and a position.

    `label_field` is a field on `component` (e.g. `interaction_type` on
    `character`) used to tag each returned entity, alongside its position.
    """
    if architect is None:
        return []
    try:
        df = architect.view(
            [f"{component}.{label_field}", "position.x", "position.y"]
        ).execute()
    except KeyError:
        return []
    return [
        (
            row["entity_id.alias"],
            row[f"{component}.{label_field}"],
            (float(row["position.x"]), float(row["position.y"])),
        )
        for _, row in df.iterrows()
    ]
