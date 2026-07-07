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
