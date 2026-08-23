#!/usr/bin/env python3
"""Find every combination of live_testing_framework's candidate_solutions
(docs/manifest/story-simulator.yaml) that together covers all seven of its
requirements.

Reads straight from the registry data -- emc2p.registrar.Registrar loading
docs/manifest + story_simulator, the same input_dirs the manifest's own
docstring names as the correct way to load it -- no new schema, just the
requirement/solution component tables that manifest already populates via
its `- requirement` tags and `- solution of: ...` links. A quick one-off
script, not a permanent audit: prints every minimal covering combination
(no solution in it is redundant) plus how many covering combinations exist
in total, then each minimal combination's own total cost (each cost type
weighted by cost_budget's normalized_value_per_unit, same weighting
resolved_impact_cost uses) and total weighted consideration value (each
consideration_rating's rating weighted by its own consideration's weight,
summed across every solution in the combination -- not per-solution, since
the combination is what a reader is actually choosing between). Run from
the repo root: `uv run python scripts/find_live_testing_solution_covers.py`.
"""

from itertools import combinations

from emc2p.registrar import Registrar

REQUIREMENTS_PREFIX = "story_simulator_mission.live_testing_framework.requirements."
SOLUTIONS_PREFIX = "story_simulator_mission.live_testing_framework.candidate_solutions."


def _leaf(path: str, prefix: str) -> str | None:
    """path's own short name if it's a direct leaf under prefix, else None
    (not under prefix at all, or prefix's own container entity)."""
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix):]
    return rest if rest and "." not in rest else None


def load_solution_map(registrar: Registrar) -> tuple[set[str], dict[str, set[str]]]:
    """(every requirement's short name, {solution's short name: requirement
    short names it solves}), read from the requirement/solution component
    tables -- not from any hand-maintained list."""
    eids = registrar.get("entity_id").execute()
    path_of = dict(zip(eids["value"].astype(str), eids["path"].astype(str)))

    req_df = registrar.get("requirement_priority").execute()
    requirements = {
        leaf
        for eid in req_df["entity_id"]
        if (leaf := _leaf(path_of[str(eid)].split(":", 1)[1], REQUIREMENTS_PREFIX))
    }

    sol_df = registrar.get("solution").execute()
    solves: dict[str, set[str]] = {}
    for _, row in sol_df.iterrows():
        source_path = path_of[str(row["entity_id"])].split(":", 1)[1]
        solution_name = _leaf(source_path, SOLUTIONS_PREFIX)
        if solution_name is None:
            continue
        target_name = _leaf(str(row["value"]), REQUIREMENTS_PREFIX)
        if target_name is None:
            continue
        solves.setdefault(solution_name, set()).add(target_name)

    return requirements, solves


def load_scoring(
    registrar: Registrar,
) -> tuple[dict[str, float], dict[str, list[tuple[str, float]]], dict[str, list[tuple[str, float]]]]:
    """(cost_budget's {cost type: normalized_value_per_unit},
    {solution name: [(cost type, raw value), ...]},
    {solution name: [(consideration axis, weight * rating), ...]})."""
    eids = registrar.get("entity_id").execute()
    path_of = dict(zip(eids["value"].astype(str), eids["path"].astype(str)))

    def solution_name(eid) -> str | None:
        return _leaf(path_of[str(eid)].split(":", 1)[1], SOLUTIONS_PREFIX)

    cost_budget_df = registrar.get("cost_budget").execute()
    cost_budget = dict(
        zip(cost_budget_df["value"], cost_budget_df["normalized_value_per_unit"].astype(float))
    )

    costs: dict[str, list[tuple[str, float]]] = {}
    for _, row in registrar.get("cost").execute().iterrows():
        name = solution_name(row["entity_id"])
        if name:
            costs.setdefault(name, []).append((row["type"], float(row["value"])))

    consideration_df = registrar.get("consideration").execute()
    weight_of = dict(zip(consideration_df["value"], consideration_df["weight"].astype(float)))
    weighted_ratings: dict[str, list[tuple[str, float]]] = {}
    for _, row in registrar.get("consideration_rating").execute().iterrows():
        name = solution_name(row["entity_id"])
        if name is None:
            continue
        axis = row["value"]
        weighted_ratings.setdefault(name, []).append((axis, weight_of[axis] * float(row["rating"])))

    return cost_budget, costs, weighted_ratings


def combo_totals(
    combo: tuple[str, ...],
    cost_budget: dict[str, float],
    costs: dict[str, list[tuple[str, float]]],
    weighted_ratings: dict[str, list[tuple[str, float]]],
) -> tuple[float, float]:
    """(total normalized cost, total weighted consideration value) summed
    across every solution in combo -- a solution shared by no other combo
    still only counts once per combo it's actually in."""
    total_cost = sum(
        raw_value * cost_budget[cost_type]
        for name in combo
        for cost_type, raw_value in costs.get(name, [])
    )
    total_consideration = sum(
        weighted for name in combo for _, weighted in weighted_ratings.get(name, [])
    )
    return total_cost, total_consideration


def find_covers(
    requirements: set[str], solves: dict[str, set[str]]
) -> tuple[list[tuple[str, ...]], list[tuple[str, ...]]]:
    """Every combination of solutions whose union covers every requirement,
    and which of those are minimal (dropping any one solution from it would
    stop covering something)."""
    names = sorted(solves)
    covers = [
        combo
        for size in range(1, len(names) + 1)
        for combo in combinations(names, size)
        if set().union(*(solves[name] for name in combo)) >= requirements
    ]
    minimal = [
        combo for combo in covers if not any(set(other) < set(combo) for other in covers)
    ]
    return covers, minimal


def main() -> None:
    registrar = Registrar.from_manifest(["docs/manifest", "story_simulator"])
    requirements, solves = load_solution_map(registrar)

    print(f"{len(requirements)} requirements: {', '.join(sorted(requirements))}\n")
    print("Each candidate solution's own coverage:")
    for name, reqs in sorted(solves.items()):
        print(f"  {name} -> {', '.join(sorted(reqs)) or '(nothing)'}")

    covers, minimal = find_covers(requirements, solves)
    print(
        f"\n{len(covers)} combinations cover all {len(requirements)} requirements; "
        f"{len(minimal)} are minimal (no solution in them is redundant):\n"
    )
    cost_budget, costs, weighted_ratings = load_scoring(registrar)
    for combo in sorted(minimal, key=len):
        total_cost, total_consideration = combo_totals(combo, cost_budget, costs, weighted_ratings)
        print(f"  ({len(combo)}) {' + '.join(combo)}")
        print(f"      total cost = {total_cost:.1f}, total weighted consideration = {total_consideration:+.2f}")


if __name__ == "__main__":
    main()
