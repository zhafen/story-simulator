#!/usr/bin/env python3
"""Generate a requirement-first HTML report of live_testing_framework's
candidate_solutions (docs/manifest/story-simulator.yaml): one section per
requirement, listing every solution that satisfies it, each expandable to
show its own pros and cons.

Requirement-first rather than solution-first on purpose -- see
docs/manifest/prioritization_reflections.yaml's fourth installment
("2026-08-22_retrospective_on_the_scoring_approach"): checking "does this
requirement have a good solution" is the direction that's actually useful,
not "what does this solution cover." Each pro/con is shown as its own
consideration_rating note, sign (positive rating = pro, negative = con),
with the qualitative `effect` field (major pro / minor pro / no effect /
minor con / major con) as a small badge alongside it rather than as the
main event -- the earlier attempt to lead with that categorical field on
its own caused confusion, not clarity.

Reuses find_live_testing_solution_covers.py's own requirement/solution
loading (same registrar tables, same prefixes, same `_leaf` helper) so
this can't silently drift out of sync with the coverage script. Prints
nothing to stdout; writes a single self-contained HTML file (no external
requests) to --output, defaulting to a scratch path outside the repo,
matching find_live_testing_solution_covers.py's own precedent of not
committing generated output, only the generator.

Run: uv run python scripts/generate_live_testing_report.py [--output PATH]
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path

from emc2p.registrar import Registrar

import find_live_testing_solution_covers as covers

REQUIREMENTS_PREFIX = covers.REQUIREMENTS_PREFIX
SOLUTIONS_PREFIX = covers.SOLUTIONS_PREFIX

DEFAULT_OUTPUT = Path("/tmp/live_testing_framework_report.html")


def load_report_data(registrar: Registrar) -> dict:
    """Everything the report needs, keyed by requirement/solution short
    name: which solutions satisfy each requirement, each entity's
    description, each solution's work_state/cost, and each solution's
    consideration_rating pros/cons (with their parent consideration's own
    description for context)."""
    requirements, solves = covers.load_solution_map(registrar)

    eids = registrar.get("entity_id").execute()
    path_of = dict(zip(eids["value"].astype(str), eids["path"].astype(str)))

    def name_of(eid, prefix: str) -> str | None:
        return covers._leaf(path_of[str(eid)].split(":", 1)[1], prefix)

    descriptions: dict[str, str] = {}
    for _, row in registrar.get("description").execute().iterrows():
        name = name_of(row["entity_id"], REQUIREMENTS_PREFIX) or name_of(
            row["entity_id"], SOLUTIONS_PREFIX
        )
        if name:
            descriptions[name] = str(row["value"])

    work_states: dict[str, str] = {}
    for _, row in registrar.get("work_state").execute().iterrows():
        name = name_of(row["entity_id"], SOLUTIONS_PREFIX)
        if name:
            work_states[name] = str(row["value"])

    costs: dict[str, list[tuple[str, float]]] = {}
    for _, row in registrar.get("cost").execute().iterrows():
        name = name_of(row["entity_id"], SOLUTIONS_PREFIX)
        if name:
            costs.setdefault(name, []).append((str(row["type"]), float(row["value"])))

    consideration_descriptions: dict[str, str] = {}
    for _, row in registrar.get("consideration").execute().iterrows():
        consideration_descriptions[str(row["value"])] = str(row["description"])

    ratings: dict[str, list[dict]] = {}
    for _, row in registrar.get("consideration_rating").execute().iterrows():
        name = name_of(row["entity_id"], SOLUTIONS_PREFIX)
        if name is None:
            continue
        effect = row["effect"]
        ratings.setdefault(name, []).append(
            {
                "axis": str(row["value"]),
                "axis_description": consideration_descriptions.get(str(row["value"]), ""),
                "note": str(row["note"]),
                "rating": float(row["rating"]),
                "effect": None if effect is None else str(effect),
            }
        )

    req_to_solutions: dict[str, list[str]] = {name: [] for name in requirements}
    for solution_name, req_names in solves.items():
        for req_name in req_names:
            req_to_solutions.setdefault(req_name, []).append(solution_name)

    return {
        "requirements": sorted(requirements),
        "req_to_solutions": {r: sorted(s) for r, s in req_to_solutions.items()},
        "descriptions": descriptions,
        "work_states": work_states,
        "costs": costs,
        "ratings": ratings,
    }


_EFFECT_CLASS = {
    "major pro": "effect-major-pro",
    "minor pro": "effect-minor-pro",
    "no effect": "effect-neutral",
    "minor con": "effect-minor-con",
    "major con": "effect-major-con",
}


def _label(name: str) -> str:
    return name.replace("_", " ")


def _render_rating(rating: dict) -> str:
    sign_label = "Pro" if rating["rating"] > 0 else "Con" if rating["rating"] < 0 else "Neutral"
    effect = rating["effect"]
    effect_html = (
        f'<span class="effect-badge {_EFFECT_CLASS.get(effect, "effect-neutral")}">{html.escape(effect)}</span>'
        if effect
        else ""
    )
    axis_title = html.escape(_label(rating["axis"]))
    axis_desc = html.escape(rating["axis_description"])
    note = html.escape(rating["note"])
    return f"""
        <li class="rating rating-{sign_label.lower()}">
          <div class="rating-head">
            <span class="sign-badge sign-{sign_label.lower()}">{sign_label}</span>
            <span class="axis-name" title="{axis_desc}">{axis_title}</span>
            {effect_html}
          </div>
          <p class="rating-note">{note}</p>
        </li>"""


def _render_solution(name: str, data: dict) -> str:
    description = html.escape(data["descriptions"].get(name, ""))
    work_state = data["work_states"].get(name, "unknown")
    cost_items = data["costs"].get(name, [])
    cost_html = (
        ", ".join(f"{value:g} {ctype}" for ctype, value in cost_items) if cost_items else "none"
    )
    ratings = sorted(data["ratings"].get(name, []), key=lambda r: -r["rating"])
    pros = [r for r in ratings if r["rating"] > 0]
    cons = [r for r in ratings if r["rating"] <= 0]
    ratings_html = "".join(_render_rating(r) for r in pros + cons)
    return f"""
      <details class="solution">
        <summary>
          <span class="solution-name">{html.escape(_label(name))}</span>
          <span class="work-state work-state-{html.escape(work_state.replace(' ', '-'))}">{html.escape(work_state)}</span>
          <span class="cost">cost: {html.escape(cost_html)}</span>
        </summary>
        <div class="solution-body">
          <p class="solution-description">{description}</p>
          <ul class="ratings">{ratings_html}</ul>
        </div>
      </details>"""


def _render_requirement(name: str, data: dict) -> str:
    description = html.escape(data["descriptions"].get(name, ""))
    solution_names = data["req_to_solutions"].get(name, [])
    if solution_names:
        solutions_html = "".join(_render_solution(s, data) for s in solution_names)
    else:
        solutions_html = '<p class="no-solutions">No candidate solution currently solves this requirement.</p>'
    return f"""
    <section class="requirement">
      <h2>{html.escape(_label(name))}</h2>
      <p class="requirement-description">{description}</p>
      {solutions_html}
    </section>"""


_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>live_testing_framework: requirements &amp; solutions</title>
<style>
  :root {{
    color-scheme: light dark;
    --bg: #ffffff; --fg: #1a1a1a; --muted: #6b7280;
    --card-bg: #f8f9fb; --border: #e2e4e9;
    --pro: #1a7f37; --pro-bg: #e6f6ea;
    --con: #b42318; --con-bg: #fdecea;
    --neutral-bg: #eef0f3; --neutral-fg: #4b5563;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #16181d; --fg: #e6e8eb;
      --card-bg: #1e2128; --border: #2c303a;
      --pro: #4fd67a; --pro-bg: #103a1c;
      --con: #ff8a80; --con-bg: #3a1310;
      --neutral-bg: #2a2d35; --neutral-fg: #9aa1ac;
    }}
  }}
  body {{
    background: var(--bg); color: var(--fg);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    max-width: 860px; margin: 0 auto; padding: 2rem 1.25rem 4rem;
    line-height: 1.5;
  }}
  h1 {{ font-size: 1.5rem; margin-bottom: 0.25rem; }}
  .subtitle {{ color: var(--muted); margin-top: 0; margin-bottom: 2.5rem; font-size: 0.95rem; }}
  .requirement {{ margin-bottom: 2.5rem; }}
  .requirement h2 {{ font-size: 1.15rem; border-bottom: 1px solid var(--border); padding-bottom: 0.4rem; }}
  .requirement-description {{ color: var(--muted); margin-top: 0.4rem; }}
  .no-solutions {{ color: var(--con); font-style: italic; }}
  details.solution {{
    background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px;
    margin: 0.6rem 0; padding: 0.1rem 1rem;
  }}
  details.solution summary {{
    cursor: pointer; padding: 0.7rem 0; display: flex; align-items: center;
    gap: 0.6rem; list-style: none; font-weight: 600;
  }}
  details.solution summary::-webkit-details-marker {{ display: none; }}
  details.solution summary::before {{ content: "▸"; color: var(--muted); font-weight: normal; }}
  details.solution[open] summary::before {{ content: "▾"; }}
  .solution-name {{ flex: 1; }}
  .work-state {{
    font-weight: 500; font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 999px;
    background: var(--neutral-bg); color: var(--neutral-fg); white-space: nowrap;
  }}
  .cost {{ font-size: 0.8rem; color: var(--muted); white-space: nowrap; font-weight: 400; }}
  .solution-body {{ padding: 0 0 1rem 1.4rem; }}
  .solution-description {{ color: var(--fg); margin-top: 0; }}
  ul.ratings {{ list-style: none; margin: 0.5rem 0 0; padding: 0; }}
  li.rating {{ padding: 0.5rem 0; border-top: 1px solid var(--border); }}
  li.rating:first-child {{ border-top: none; }}
  .rating-head {{ display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }}
  .sign-badge {{ font-size: 0.7rem; font-weight: 700; padding: 0.1rem 0.45rem; border-radius: 4px; }}
  .sign-pro {{ background: var(--pro-bg); color: var(--pro); }}
  .sign-con {{ background: var(--con-bg); color: var(--con); }}
  .sign-neutral {{ background: var(--neutral-bg); color: var(--neutral-fg); }}
  .axis-name {{ font-weight: 600; }}
  .effect-badge {{
    font-size: 0.68rem; padding: 0.05rem 0.4rem; border-radius: 999px; font-weight: 500;
    margin-left: auto;
  }}
  .effect-major-pro {{ background: var(--pro-bg); color: var(--pro); }}
  .effect-minor-pro {{ background: var(--pro-bg); color: var(--pro); opacity: 0.75; }}
  .effect-neutral {{ background: var(--neutral-bg); color: var(--neutral-fg); }}
  .effect-minor-con {{ background: var(--con-bg); color: var(--con); opacity: 0.75; }}
  .effect-major-con {{ background: var(--con-bg); color: var(--con); }}
  .rating-note {{ margin: 0.3rem 0 0; color: var(--muted); font-size: 0.92rem; }}
</style>
</head>
<body>
  <h1>live_testing_framework: requirements &amp; solutions</h1>
  <p class="subtitle">
    Generated by scripts/generate_live_testing_report.py from
    docs/manifest/story-simulator.yaml. One section per requirement;
    click a solution to expand its pros and cons.
  </p>
  {requirements_html}
</body>
</html>
"""


def render_report(data: dict) -> str:
    requirements_html = "".join(_render_requirement(r, data) for r in data["requirements"])
    return _PAGE_TEMPLATE.format(requirements_html=requirements_html)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    registrar = Registrar.from_manifest(["docs/manifest", "story_simulator"])
    data = load_report_data(registrar)
    args.output.write_text(render_report(data))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
