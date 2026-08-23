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
consideration_rating note, labeled Pro/Con by the sign of its own
consideration's `weight` times its `rating` (not by rating's sign alone --
a negative rating on a negative-weight axis nets positive), with the raw
weight and rating values shown alongside rather than the qualitative
`effect` field -- the earlier attempt to lead with that categorical field
on its own caused confusion, not clarity, so it's set aside here (still
recorded on each consideration_rating, just not surfaced by this report).

Reuses find_live_testing_solution_covers.py's own requirement/solution
loading (same registrar tables, same prefixes, same `_leaf` helper) so
this can't silently drift out of sync with the coverage script. Prints
nothing to stdout; writes a single self-contained HTML file (no external
requests except the Google Fonts stylesheet) to --output, defaulting to a
scratch path outside the repo, matching find_live_testing_solution_covers.py's
own precedent of not committing generated output, only the generator.

--fragment writes just the title/style/body content, without the
surrounding <!doctype>/<html>/<head>/<body> tags -- for publishing as a
Claude Artifact, which wraps that skeleton on its own and rejects one of
its own. Omit --fragment for a normal, directly-openable standalone page.

Run: uv run python scripts/generate_live_testing_report.py [--output PATH] [--fragment]
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
    consideration_weights: dict[str, float] = {}
    for _, row in registrar.get("consideration").execute().iterrows():
        axis = str(row["value"])
        consideration_descriptions[axis] = str(row["description"])
        consideration_weights[axis] = float(row["weight"])

    ratings: dict[str, list[dict]] = {}
    for _, row in registrar.get("consideration_rating").execute().iterrows():
        name = name_of(row["entity_id"], SOLUTIONS_PREFIX)
        if name is None:
            continue
        axis = str(row["value"])
        weight = consideration_weights.get(axis, 0.0)
        rating = float(row["rating"])
        ratings.setdefault(name, []).append(
            {
                "axis": axis,
                "axis_description": consideration_descriptions.get(axis, ""),
                "note": str(row["note"]),
                "weight": weight,
                "rating": rating,
                "contribution": weight * rating,
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


def _label(name: str) -> str:
    return name.replace("_", " ")


def _render_rating(rating: dict) -> str:
    contribution = rating["contribution"]
    sign_label = "Pro" if contribution > 0 else "Con" if contribution < 0 else "Neutral"
    axis_title = html.escape(_label(rating["axis"]))
    axis_desc = html.escape(rating["axis_description"])
    note = html.escape(rating["note"])
    values = (
        f'weight {rating["weight"]:+.2g} &times; rating {rating["rating"]:+.2g} '
        f'= <strong>{contribution:+.2g}</strong>'
    )
    return f"""
        <li class="rating rating-{sign_label.lower()}">
          <div class="rating-head">
            <span class="sign-badge sign-{sign_label.lower()}">{sign_label}</span>
            <span class="axis-name" title="{axis_desc}">{axis_title}</span>
            <span class="values">{values}</span>
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
    ratings = sorted(data["ratings"].get(name, []), key=lambda r: -r["contribution"])
    pros = [r for r in ratings if r["contribution"] > 0]
    cons = [r for r in ratings if r["contribution"] <= 0]
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
      <p class="eyebrow">Requirement</p>
      <h2>{html.escape(_label(name))}</h2>
      <p class="requirement-description">{description}</p>
      {solutions_html}
    </section>"""


_FONTS_LINK = (
    '<link rel="stylesheet" '
    'href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500;600'
    '&family=IBM+Plex+Sans:wght@400;500;600&display=swap">'
)

_STYLE = """
  :root {
    color-scheme: light dark;
    --bg: #f7f6f2; --surface: #ffffff; --border: #e2ded2;
    --fg: #1e211d; --muted: #6b6f63; --muted-2: #8a8d80;
    --accent: #0f6e67; --accent-fg: #ffffff;
    --pro: #2e6b45; --pro-bg: #e4f1e7;
    --con: #a3392c; --con-bg: #f8e9e5;
    --chip-bg: #ece9dd; --chip-fg: #55584c;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #161816; --surface: #1e211d; --border: #33362e;
      --fg: #eae8de; --muted: #a3a695; --muted-2: #7d8071;
      --accent: #4fb8ae; --accent-fg: #0d1513;
      --pro: #7bc794; --pro-bg: #1c2e21;
      --con: #e08b7c; --con-bg: #34211d;
      --chip-bg: #2a2d26; --chip-fg: #b9bcae;
    }
  }
  :root[data-theme="dark"] {
    --bg: #161816; --surface: #1e211d; --border: #33362e;
    --fg: #eae8de; --muted: #a3a695; --muted-2: #7d8071;
    --accent: #4fb8ae; --accent-fg: #0d1513;
    --pro: #7bc794; --pro-bg: #1c2e21;
    --con: #e08b7c; --con-bg: #34211d;
    --chip-bg: #2a2d26; --chip-fg: #b9bcae;
  }

  * { box-sizing: border-box; }

  body {
    background: var(--bg); color: var(--fg);
    font-family: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    max-width: 760px; margin: 0 auto; padding: 3rem 1.5rem 5rem;
    line-height: 1.55;
    -webkit-font-smoothing: antialiased;
  }

  .masthead { margin-bottom: 2.75rem; }
  .kicker {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--accent); margin: 0 0 0.6rem;
  }
  h1 {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 1.7rem; font-weight: 600; margin: 0 0 0.6rem;
    text-wrap: balance; letter-spacing: -0.01em;
  }
  .subtitle { color: var(--muted); margin: 0; font-size: 0.95rem; max-width: 62ch; }

  .requirement { margin-bottom: 2.25rem; padding-bottom: 2.25rem; border-bottom: 1px solid var(--border); }
  .requirement:last-child { border-bottom: none; }
  .eyebrow {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.68rem; font-weight: 600; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--muted-2); margin: 0 0 0.35rem;
  }
  .requirement h2 {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 1.15rem; font-weight: 600; margin: 0; text-wrap: balance;
  }
  .requirement-description { color: var(--muted); margin: 0.5rem 0 1.1rem; max-width: 62ch; }
  .no-solutions { color: var(--con); font-style: italic; }

  details.solution {
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    margin: 0.7rem 0; padding: 0 1.1rem;
  }
  details.solution summary {
    cursor: pointer; padding: 0.85rem 0; display: flex; align-items: center;
    gap: 0.7rem; list-style: none; font-weight: 600;
  }
  details.solution summary::-webkit-details-marker { display: none; }
  details.solution summary::before {
    content: "▸"; color: var(--muted-2); font-weight: normal; flex-shrink: 0;
    transition: transform 0.15s ease;
  }
  details.solution[open] summary::before { transform: rotate(90deg); }
  .solution-name { flex: 1; font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 0.95rem; }
  .work-state {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-weight: 500; font-size: 0.68rem; letter-spacing: 0.03em;
    padding: 0.2rem 0.55rem; border-radius: 999px;
    background: var(--chip-bg); color: var(--chip-fg); white-space: nowrap;
  }
  .cost {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-variant-numeric: tabular-nums;
    font-size: 0.78rem; color: var(--muted); white-space: nowrap; font-weight: 400;
  }
  .solution-body { padding: 0 0 1.1rem 1.5rem; }
  .solution-description { color: var(--fg); margin-top: 0; }
  ul.ratings { list-style: none; margin: 0.6rem 0 0; padding: 0; }
  li.rating { padding: 0.6rem 0; border-top: 1px solid var(--border); }
  li.rating:first-child { border-top: none; }
  .rating-head { display: flex; align-items: center; gap: 0.55rem; flex-wrap: wrap; }
  .sign-badge {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.66rem; font-weight: 600; letter-spacing: 0.04em;
    padding: 0.12rem 0.5rem; border-radius: 5px;
  }
  .sign-pro { background: var(--pro-bg); color: var(--pro); }
  .sign-con { background: var(--con-bg); color: var(--con); }
  .sign-neutral { background: var(--chip-bg); color: var(--chip-fg); }
  .axis-name { font-weight: 600; }
  .values {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-variant-numeric: tabular-nums;
    font-size: 0.74rem; color: var(--muted); margin-left: auto; white-space: nowrap;
  }
  .values strong { color: var(--fg); }
  .rating-note { margin: 0.35rem 0 0; color: var(--muted); font-size: 0.92rem; max-width: 62ch; }

  @media (max-width: 480px) {
    .values { margin-left: 0; }
  }
"""

_TITLE = "Live Testing Framework"

_BODY_TEMPLATE = """<title>{title}</title>
{fonts_link}
<style>{style}</style>
  <div class="masthead">
    <p class="kicker">live_testing_framework &middot; requirement coverage</p>
    <h1>Requirements &amp; candidate solutions</h1>
    <p class="subtitle">
      One section per requirement, listing every candidate solution that
      satisfies it. Expand a solution to see its pros and cons.
    </p>
  </div>
  {requirements_html}
"""


def render_content(data: dict) -> str:
    """Title + fonts link + style + body content, no surrounding document
    tags -- for publishing as a Claude Artifact (which wraps its own
    <!doctype>/<html>/<head>/<body> and rejects one of its own)."""
    requirements_html = "".join(_render_requirement(r, data) for r in data["requirements"])
    return _BODY_TEMPLATE.format(
        title=html.escape(_TITLE), fonts_link=_FONTS_LINK, style=_STYLE, requirements_html=requirements_html
    )


def render_report(data: dict) -> str:
    """A full, directly-openable standalone HTML document."""
    requirements_html = "".join(_render_requirement(r, data) for r in data["requirements"])
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(_TITLE)}</title>
{_FONTS_LINK}
<style>{_STYLE}</style>
</head>
<body>
  <div class="masthead">
    <p class="kicker">live_testing_framework &middot; requirement coverage</p>
    <h1>Requirements &amp; candidate solutions</h1>
    <p class="subtitle">
      One section per requirement, listing every candidate solution that
      satisfies it. Expand a solution to see its pros and cons.
    </p>
  </div>
  {requirements_html}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--fragment", action="store_true",
        help="Write title/style/body content only, for publishing as a Claude Artifact.",
    )
    args = parser.parse_args()

    registrar = Registrar.from_manifest(["docs/manifest", "story_simulator"])
    data = load_report_data(registrar)
    content = render_content(data) if args.fragment else render_report(data)
    args.output.write_text(content)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
